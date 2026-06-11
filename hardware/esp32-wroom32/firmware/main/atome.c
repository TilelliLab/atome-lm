/*
 * atome.c — ATOME ternary inference engine implementation
 *
 * Pure C99, zero heap, fixed buffers. Runs on bare metal.
 * The matmul kernel does ZERO float multiplies — only add/sub/skip.
 *
 * Copyright (c) 2026 Atome LM contributors (atomelm.com).
 * SPDX-License-Identifier: Apache-2.0
 */

#include "atome.h"
#include <math.h>
#include <string.h>

/* ================================================================
 * Ternary matrix-vector multiply
 *
 * y[j] = scale * sum_i { trit(W,j,i) * x[i] }
 *
 * trit is in {-1, 0, +1}, so:
 *   +1 => y[j] += x[i]
 *   -1 => y[j] -= x[i]
 *    0 => skip
 *
 * ZERO float multiplies in the inner loop. This is the whole point.
 * ================================================================ */

void atome_ternary_matvec(
    const atome_ternary_t* W,
    const float* x,
    float* out
) {
    const int rows = W->rows;
    const int cols = W->cols;
    const uint8_t* packed = W->packed;
    const float scale = W->scale;

    for (int j = 0; j < rows; ++j) {
        float acc = 0.0f;
        const int row_offset = j * cols;

        for (int i = 0; i < cols; ++i) {
            int8_t w = atome_unpack_trit(packed, row_offset + i);
            if (w == 1)       acc += x[i];
            else if (w == -1) acc -= x[i];
            /* w == 0: skip — the beauty of ternary */
        }

        out[j] = acc * scale;
    }
}

/* ================================================================
 * Layer normalization
 * ================================================================ */

void atome_layer_norm(float* x, int dim, const atome_norm_t* params) {
    const float eps = 1e-5f;

    /* Mean */
    float mean = 0.0f;
    for (int i = 0; i < dim; ++i) mean += x[i];
    mean /= (float)dim;

    /* Variance */
    float var = 0.0f;
    for (int i = 0; i < dim; ++i) {
        float d = x[i] - mean;
        var += d * d;
    }
    var /= (float)dim;

    /* Normalize */
    float inv_std = 1.0f / sqrtf(var + eps);
    for (int i = 0; i < dim; ++i) {
        x[i] = params->gamma[i] * (x[i] - mean) * inv_std + params->beta[i];
    }
}

/* ================================================================
 * Causal depthwise conv1d (ternary kernel)
 * ================================================================ */

void atome_causal_conv(
    const float x[][ATOME_D_MODEL],
    int seq_len,
    const atome_conv_t* kernel,
    float out[][ATOME_D_MODEL]
) {
    const int ch = kernel->channels;
    const int ks = kernel->kernel_size;
    const float scale = kernel->scale;

    for (int t = 0; t < seq_len; ++t) {
        for (int c = 0; c < ch; ++c) {
            float acc = 0.0f;
            for (int k = 0; k < ks; ++k) {
                int src_t = t - k;
                if (src_t < 0) continue;
                int8_t w = atome_unpack_trit(kernel->packed, c * ks + k);
                if (w == 1)       acc += x[src_t][c];
                else if (w == -1) acc -= x[src_t][c];
            }
            out[t][c] = acc * scale;
        }
    }
}

/* ================================================================
 * Diagonal SSM recurrent
 *
 * h[c] = tanh(a[c]) * h[c] + b[c] * x[t][c]
 * y[t][c] = c_out[c] * h[c]
 * ================================================================ */

void atome_ssm_forward(
    const float x[][ATOME_D_MODEL],
    int seq_len,
    const atome_ssm_t* params,
    float* h,
    float out[][ATOME_D_MODEL]
) {
    const int C = params->channels;

    for (int t = 0; t < seq_len; ++t) {
        for (int c = 0; c < C; ++c) {
            float a = tanhf(params->a[c]);
            h[c] = a * h[c] + params->b[c] * x[t][c];
            out[t][c] = params->c_out[c] * h[c];
        }
    }
}

/* ================================================================
 * Softmax (small array, in-place)
 * ================================================================ */

static void atome_softmax(float* x, int n) {
    float max_val = x[0];
    for (int i = 1; i < n; ++i) {
        if (x[i] > max_val) max_val = x[i];
    }
    float sum = 0.0f;
    for (int i = 0; i < n; ++i) {
        x[i] = expf(x[i] - max_val);
        sum += x[i];
    }
    float inv = 1.0f / (sum + 1e-10f);
    for (int i = 0; i < n; ++i) {
        x[i] *= inv;
    }
}

/* ================================================================
 * Sparse causal attention
 * ================================================================ */

void atome_sparse_attn(
    const float x[][ATOME_D_MODEL],
    int seq_len,
    const atome_attn_t* params,
    atome_state_t* state,
    float out[][ATOME_D_MODEL]
) {
    const int d_h = params->d_head;
    const int d_m = ATOME_D_MODEL;
    const int top_k = params->top_k;

    /* Project K, V for all positions into cache */
    for (int t = 0; t < seq_len; ++t) {
        atome_ternary_matvec(&params->Wk, x[t], state->k_cache[t]);
        atome_ternary_matvec(&params->Wv, x[t], state->v_cache[t]);
    }

    for (int t = 0; t < seq_len; ++t) {
        /* Project Q for this position */
        atome_ternary_matvec(&params->Wq, x[t], state->q);

        /* Compute attention scores: Q[t] . K[j] for j <= t */
        int n_past = t + 1;
        float scale = 1.0f / sqrtf((float)d_h);
        for (int j = 0; j < n_past; ++j) {
            float s = 0.0f;
            for (int d = 0; d < d_h; ++d) {
                s += state->q[d] * state->k_cache[j][d];
            }
            state->attn_scores[j] = s * scale;
        }

        /* Top-k selection (simple insertion sort for small k) */
        int k_eff = (top_k < n_past) ? top_k : n_past;
        int top_idx[ATOME_TOP_K];
        float top_scores[ATOME_TOP_K];

        for (int i = 0; i < k_eff; ++i) {
            top_idx[i] = -1;
            top_scores[i] = -1e30f;
        }

        for (int j = 0; j < n_past; ++j) {
            float s = state->attn_scores[j];
            /* Insert into sorted top-k */
            if (s > top_scores[k_eff - 1]) {
                top_scores[k_eff - 1] = s;
                top_idx[k_eff - 1] = j;
                /* Bubble up */
                for (int i = k_eff - 1; i > 0 && top_scores[i] > top_scores[i-1]; --i) {
                    float ts = top_scores[i]; top_scores[i] = top_scores[i-1]; top_scores[i-1] = ts;
                    int ti = top_idx[i]; top_idx[i] = top_idx[i-1]; top_idx[i-1] = ti;
                }
            }
        }

        /* Softmax over top-k scores */
        atome_softmax(top_scores, k_eff);

        /* Weighted sum of V */
        memset(out[t], 0, d_m * sizeof(float));
        for (int i = 0; i < k_eff; ++i) {
            float w = top_scores[i];
            int idx = top_idx[i];
            for (int d = 0; d < d_m; ++d) {
                out[t][d] += w * state->v_cache[idx][d];
            }
        }
    }
}

/* ================================================================
 * Block forward: norm -> per-token router -> pathways -> mix -> residual
 *
 * FIXED: router now computes per-token weights (not last-token-for-all).
 * FIXED: pathway scratch buffers live in atome_state_t (not stack).
 * ================================================================ */

static void atome_block_forward(
    const atome_block_t* block,
    atome_state_t* state,
    int seq_len,
    int layer_idx
) {
    const int d = ATOME_D_MODEL;
    const int np = ATOME_N_PATHWAYS;

    /* Normalize input into state->normed */
    memcpy(state->normed, state->x, seq_len * d * sizeof(float));
    for (int t = 0; t < seq_len; ++t) {
        atome_layer_norm(state->normed[t], d, &block->norm);
    }

    /* Per-token router: compute pathway weights for EVERY token */
    for (int t = 0; t < seq_len; ++t) {
        atome_ternary_matvec(&block->router, state->normed[t], state->router_w[t]);
        atome_softmax(state->router_w[t], np);
    }

    /* Local conv pathway */
    atome_causal_conv(state->normed, seq_len, &block->local_conv, state->path_local);

    /* SSM pathway — uses persistent per-layer hidden state */
    atome_ssm_forward(state->normed, seq_len, &block->ssm,
                      state->ssm_h[layer_idx], state->path_ssm);

    /* Sparse attention pathway */
    atome_sparse_attn(state->normed, seq_len, &block->attn, state, state->path_attn);

    /* Mix by per-token router weights + residual */
    for (int t = 0; t < seq_len; ++t) {
        for (int i = 0; i < d; ++i) {
            float mixed = state->router_w[t][0] * state->path_local[t][i]
                        + state->router_w[t][1] * state->path_ssm[t][i]
                        + state->router_w[t][2] * state->path_attn[t][i];
            state->x[t][i] += mixed;
        }
    }
}

/* ================================================================
 * High-level API
 * ================================================================ */

void atome_init(atome_state_t* state) {
    memset(state, 0, sizeof(atome_state_t));
}

int atome_predict_next(
    const atome_model_t* model,
    atome_state_t* state,
    const int* tokens,
    int n_tokens
) {
    const int d = ATOME_D_MODEL;
    const int V = ATOME_VOCAB_SIZE;

    /* Reject invalid lengths: n_tokens < 1 would index state->x[-1]
     * at the final-norm step and read garbage logits. */
    if (!model || !state || !tokens || n_tokens < 1) return -1;
    if (n_tokens > ATOME_MAX_SEQ) n_tokens = ATOME_MAX_SEQ;

    /* predict_next reprocesses the FULL token list each call. SSM hidden
     * state must therefore start at zero — otherwise residual h from a
     * prior call re-consumes tokens we've already consumed and silently
     * pollutes the forward pass. This is the fix for the multi-token
     * parity divergence documented in test_parity_multitoken.py. */
    for (int layer = 0; layer < ATOME_N_LAYERS; ++layer) {
        memset(state->ssm_h[layer], 0, ATOME_D_MODEL * sizeof(float));
    }

    /* Embedding lookup */
    for (int t = 0; t < n_tokens; ++t) {
        int tok = tokens[t];
        if (tok < 0 || tok >= V) tok = 0;
        /* Ternary embedding: unpack row tok from embed */
        const int row_offset = tok * d;
        for (int i = 0; i < d; ++i) {
            int8_t w = atome_unpack_trit(model->embed.packed, row_offset + i);
            state->x[t][i] = (float)w * model->embed.scale;
        }
    }

    /* Blocks — SSM hidden state is reset above and re-derived each call from
     * the full token prefix. This keeps multi-token generation deterministic
     * and bit-exact with Python (see test_parity_multitoken.py). */
    for (int layer = 0; layer < ATOME_N_LAYERS; ++layer) {
        atome_block_forward(&model->blocks[layer], state, n_tokens, layer);
    }

    /* Final norm on last position */
    atome_layer_norm(state->x[n_tokens - 1], d, &model->final_norm);

    /* Unembed: compute logits */
    atome_ternary_matvec(&model->unembed, state->x[n_tokens - 1], state->logits);

    /* Argmax */
    int best = 0;
    float best_val = state->logits[0];
    for (int i = 1; i < V; ++i) {
        if (state->logits[i] > best_val) {
            best_val = state->logits[i];
            best = i;
        }
    }

    return best;
}

const float* atome_get_logits(atome_state_t* state) {
    return state->logits;
}

int atome_generate(
    const atome_model_t* model,
    atome_state_t* state,
    const int* prompt,
    int prompt_len,
    int* output,
    int max_tokens
) {
    int tokens[ATOME_MAX_SEQ];
    int n = prompt_len;

    /* Reject invalid inputs before memcpy / generation loop. */
    if (!model || !state || !prompt || !output) return 0;
    if (prompt_len < 1 || max_tokens < 1) return 0;
    if (n > ATOME_MAX_SEQ) n = ATOME_MAX_SEQ;
    memcpy(tokens, prompt, n * sizeof(int));

    /* Reset SSM state for a fresh generation */
    for (int layer = 0; layer < ATOME_N_LAYERS; ++layer) {
        memset(state->ssm_h[layer], 0, ATOME_D_MODEL * sizeof(float));
    }

    int generated = 0;
    while (generated < max_tokens && n < ATOME_MAX_SEQ) {
        int next = atome_predict_next(model, state, tokens, n);
        tokens[n] = next;
        output[generated] = next;
        n++;
        generated++;
    }

    return generated;
}

/* ================================================================
 * Forward declarations for binary loader helpers.
 *
 * All readers take an `end` pointer (one past the last valid byte of
 * the input buffer) and return NULL on overflow. Callers must check
 * the return value and abort the load if NULL. This replaces an older
 * design that advanced the pointer with no remaining-length check —
 * a truncated or corrupt .atome file would read past the buffer and
 * silently interpret garbage as model weights.
 * ================================================================ */
static const uint8_t* read_ternary(const uint8_t* ptr, const uint8_t* end, atome_ternary_t* t, int rows, int cols);
static const uint8_t* read_conv(const uint8_t* ptr, const uint8_t* end, atome_conv_t* c, int channels, int ks);
static const uint8_t* read_norm(const uint8_t* ptr, const uint8_t* end, atome_norm_t* n, int dim);
static const uint8_t* read_ssm(const uint8_t* ptr, const uint8_t* end, atome_ssm_t* s, int channels);

/* Advance ptr through a reader; return -2 on overflow. */
#define READ_OR_FAIL(call) do { ptr = (call); if (!ptr) return -2; } while (0)

/* Forward declaration for block forward */
static void atome_block_forward(const atome_block_t* block, atome_state_t* state, int seq_len, int layer_idx);

/* ================================================================
 * Classification head
 * ================================================================ */

int atome_classify(
    const atome_classifier_t* clf,
    atome_state_t* state,
    const int* tokens,
    int n_tokens,
    float* class_logits
) {
    const int d = ATOME_D_MODEL;

    if (n_tokens > ATOME_MAX_SEQ) n_tokens = ATOME_MAX_SEQ;

    /* Reset SSM hidden state — same invariant as atome_predict_next.
     * Without this, classification is stateful across calls: residual h from
     * a prior classify() leaks into the next forward and silently changes the
     * predicted class for the same input. */
    for (int layer = 0; layer < ATOME_N_LAYERS; ++layer) {
        memset(state->ssm_h[layer], 0, ATOME_D_MODEL * sizeof(float));
    }

    /* Run base model forward (embedding + blocks + final norm) */
    /* Embedding */
    for (int t = 0; t < n_tokens; ++t) {
        int tok = tokens[t];
        if (tok < 0 || tok >= ATOME_VOCAB_SIZE) tok = 0;
        const int row_offset = tok * d;
        for (int i = 0; i < d; ++i) {
            int8_t w = atome_unpack_trit(clf->base.embed.packed, row_offset + i);
            state->x[t][i] = (float)w * clf->base.embed.scale;
        }
    }

    for (int layer = 0; layer < ATOME_N_LAYERS; ++layer) {
        atome_block_forward(&clf->base.blocks[layer], state, n_tokens, layer);
    }

    atome_layer_norm(state->x[n_tokens - 1], d, &clf->base.final_norm);

    /* Classification head: logits = head @ last_hidden */
    float head_logits[ATOME_MAX_CLASSES];
    atome_ternary_matvec(&clf->head, state->x[n_tokens - 1], head_logits);

    if (class_logits) {
        memcpy(class_logits, head_logits, clf->n_classes * sizeof(float));
    }

    /* Argmax */
    int best = 0;
    float best_val = head_logits[0];
    for (int i = 1; i < clf->n_classes; ++i) {
        if (head_logits[i] > best_val) {
            best_val = head_logits[i];
            best = i;
        }
    }
    return best;
}

int atome_classifier_load(atome_classifier_t* clf, const uint8_t* data, size_t len) {
    const uint8_t* ptr = data;
    const uint8_t* end = data + len;

    /* Check magic + n_classes header */
    if (len < 9 + sizeof(int) || memcmp(ptr, "ATOMECL01", 9) != 0) return -1;
    ptr += 9;
    memcpy(&clf->n_classes, ptr, sizeof(int));
    ptr += sizeof(int);
    if (clf->n_classes <= 0 || clf->n_classes > ATOME_MAX_CLASSES) return -1;

    const int d = ATOME_D_MODEL;
    const int V = ATOME_VOCAB_SIZE;
    const int dh = ATOME_D_HEAD;
    const int ks = ATOME_KERNEL_SIZE;

    /* Embedding */
    READ_OR_FAIL(read_ternary(ptr, end, &clf->base.embed, V, d));

    /* Blocks */
    for (int layer = 0; layer < ATOME_N_LAYERS; ++layer) {
        atome_block_t* blk = &clf->base.blocks[layer];
        READ_OR_FAIL(read_norm(ptr, end, &blk->norm, d));
        READ_OR_FAIL(read_conv(ptr, end, &blk->local_conv, d, ks));
        READ_OR_FAIL(read_ssm(ptr, end, &blk->ssm, d));
        READ_OR_FAIL(read_ternary(ptr, end, &blk->attn.Wq, dh, d));
        READ_OR_FAIL(read_ternary(ptr, end, &blk->attn.Wk, dh, d));
        READ_OR_FAIL(read_ternary(ptr, end, &blk->attn.Wv, d, d));
        blk->attn.d_head = dh;
        blk->attn.top_k = ATOME_TOP_K;
        READ_OR_FAIL(read_ternary(ptr, end, &blk->router, ATOME_N_PATHWAYS, d));
    }

    /* Final norm */
    READ_OR_FAIL(read_norm(ptr, end, &clf->base.final_norm, d));

    /* Unembed (skip — classifier doesn't need it, but it's in the binary) */
    atome_ternary_t dummy_unembed;
    READ_OR_FAIL(read_ternary(ptr, end, &dummy_unembed, V, d));

    /* Classification head */
    READ_OR_FAIL(read_ternary(ptr, end, &clf->head, clf->n_classes, d));

    return 0;
}

/* ================================================================
 * Binary checkpoint loader
 *
 * Format: "ATOME01" magic + packed weights in fixed order
 * All ternary weights are 2-bit packed (4 per byte)
 * Float params (norms, SSM) stored as float32
 * ================================================================ */

static const uint8_t* read_ternary(const uint8_t* ptr, const uint8_t* end, atome_ternary_t* t, int rows, int cols) {
    int n_trits = rows * cols;
    int n_bytes = (n_trits + 3) / 4;
    if (ptr + sizeof(float) + n_bytes > end) return NULL;
    t->rows = (uint16_t)rows;
    t->cols = (uint16_t)cols;
    memcpy(&t->scale, ptr, sizeof(float));
    ptr += sizeof(float);
    t->packed = ptr;
    ptr += n_bytes;
    return ptr;
}

static const uint8_t* read_conv(const uint8_t* ptr, const uint8_t* end, atome_conv_t* c, int channels, int ks) {
    int n_trits = channels * ks;
    int n_bytes = (n_trits + 3) / 4;
    if (ptr + sizeof(float) + n_bytes > end) return NULL;
    c->channels = (uint16_t)channels;
    c->kernel_size = (uint16_t)ks;
    memcpy(&c->scale, ptr, sizeof(float));
    ptr += sizeof(float);
    c->packed = ptr;
    ptr += n_bytes;
    return ptr;
}

static const uint8_t* read_norm(const uint8_t* ptr, const uint8_t* end, atome_norm_t* n, int dim) {
    if (ptr + 2 * dim * sizeof(float) > end) return NULL;
    n->gamma = (const float*)ptr;
    ptr += dim * sizeof(float);
    n->beta = (const float*)ptr;
    ptr += dim * sizeof(float);
    return ptr;
}

static const uint8_t* read_ssm(const uint8_t* ptr, const uint8_t* end, atome_ssm_t* s, int channels) {
    if (ptr + 3 * channels * sizeof(float) > end) return NULL;
    s->channels = (uint16_t)channels;
    s->a = (const float*)ptr;
    ptr += channels * sizeof(float);
    s->b = (const float*)ptr;
    ptr += channels * sizeof(float);
    s->c_out = (const float*)ptr;
    ptr += channels * sizeof(float);
    return ptr;
}

int atome_load(atome_model_t* model, const uint8_t* data, size_t len) {
    const uint8_t* ptr = data;
    const uint8_t* end = data + len;

    /* Check magic */
    if (len < 7 || memcmp(ptr, "ATOME01", 7) != 0) return -1;
    ptr += 7;

    const int d = ATOME_D_MODEL;
    const int V = ATOME_VOCAB_SIZE;
    const int dh = ATOME_D_HEAD;
    const int ks = ATOME_KERNEL_SIZE;

    /* Embedding */
    READ_OR_FAIL(read_ternary(ptr, end, &model->embed, V, d));

    /* Blocks */
    for (int layer = 0; layer < ATOME_N_LAYERS; ++layer) {
        atome_block_t* blk = &model->blocks[layer];

        READ_OR_FAIL(read_norm(ptr, end, &blk->norm, d));
        READ_OR_FAIL(read_conv(ptr, end, &blk->local_conv, d, ks));
        READ_OR_FAIL(read_ssm(ptr, end, &blk->ssm, d));

        READ_OR_FAIL(read_ternary(ptr, end, &blk->attn.Wq, dh, d));
        READ_OR_FAIL(read_ternary(ptr, end, &blk->attn.Wk, dh, d));
        READ_OR_FAIL(read_ternary(ptr, end, &blk->attn.Wv, d, d));
        blk->attn.d_head = dh;
        blk->attn.top_k = ATOME_TOP_K;

        READ_OR_FAIL(read_ternary(ptr, end, &blk->router, ATOME_N_PATHWAYS, d));
    }

    /* Final norm */
    READ_OR_FAIL(read_norm(ptr, end, &model->final_norm, d));

    /* Unembed */
    READ_OR_FAIL(read_ternary(ptr, end, &model->unembed, V, d));

    return 0;
}

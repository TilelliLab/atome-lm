/*
 * atome.h — ATOME: Ternary inference engine for microcontrollers
 *
 * Zero-dependency, zero-heap, pure integer matmul.
 * Designed for ESP32, STM32, RP2040, and anything with >8KB RAM.
 *
 * Usage:
 *   #define ATOME_D_MODEL    64
 *   #define ATOME_MAX_SEQ    32
 *   #define ATOME_N_LAYERS   4
 *   #define ATOME_N_PATHWAYS 3
 *   #include "atome.h"
 *
 *   atome_model_t model;
 *   atome_load_from_flash(&model, flash_ptr);
 *   int tokens[32] = {72, 101, 108, 108, 111};  // "Hello"
 *   int next = atome_predict_next(&model, tokens, 5);
 *
 * Copyright (c) 2026 Atome LM contributors (atomelm.com).
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef ATOME_H
#define ATOME_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stddef.h>

/* ================================================================
 * Compile-time configuration — override before #include
 * ================================================================ */

#ifndef ATOME_D_MODEL
#define ATOME_D_MODEL       64      /* embedding dimension */
#endif

#ifndef ATOME_MAX_SEQ
#define ATOME_MAX_SEQ       32      /* max sequence length */
#endif

#ifndef ATOME_N_LAYERS
#define ATOME_N_LAYERS      4       /* number of blocks */
#endif

#ifndef ATOME_N_PATHWAYS
#define ATOME_N_PATHWAYS    3       /* 3=Local+State+Sparse, 5=full */
#endif

#ifndef ATOME_VOCAB_SIZE
#define ATOME_VOCAB_SIZE    256     /* byte-level tokenizer */
#endif

#ifndef ATOME_D_HEAD
#define ATOME_D_HEAD        16      /* attention head dim */
#endif

#ifndef ATOME_KERNEL_SIZE
#define ATOME_KERNEL_SIZE   5       /* local conv kernel */
#endif

#ifndef ATOME_TOP_K
#define ATOME_TOP_K         4       /* sparse attention top-k */
#endif

/* Derived constants */
#define ATOME_D_INNER       (ATOME_D_MODEL * 2)  /* FFN expansion (if 5 pathways) */

/* ================================================================
 * Ternary weight storage — 2 bits per weight, packed into bytes
 * Encoding: 00 = 0, 01 = +1, 11 = -1
 * 4 weights per byte = 4x compression vs int8
 * ================================================================ */

/* Packed ternary: 4 weights per byte */
typedef struct {
    const uint8_t* packed;  /* points into flash/ROM */
    float scale;            /* alpha from training */
    uint16_t rows;
    uint16_t cols;
} atome_ternary_t;

/* Extract one trit from packed format */
static inline int8_t atome_unpack_trit(const uint8_t* packed, int idx) {
    int byte_idx = idx >> 2;       /* idx / 4 */
    int bit_pos = (idx & 3) << 1;  /* (idx % 4) * 2 */
    uint8_t bits = (packed[byte_idx] >> bit_pos) & 0x03;
    /* 00 -> 0, 01 -> +1, 11 -> -1 */
    if (bits == 0x01) return 1;
    if (bits == 0x03) return -1;
    return 0;
}

/* ================================================================
 * Layer parameters
 * ================================================================ */

/* Causal conv kernel (depthwise) */
typedef struct {
    const uint8_t* packed;  /* (channels * kernel_size) trits, packed */
    float scale;
    uint16_t channels;
    uint16_t kernel_size;
} atome_conv_t;

/* Diagonal SSM */
typedef struct {
    const float* a;      /* decay (pre-tanh), [channels] */
    const float* b;      /* input gain, [channels] */
    const float* c_out;  /* output scale, [channels] */
    uint16_t channels;
} atome_ssm_t;

/* Sparse attention */
typedef struct {
    atome_ternary_t Wq;   /* (d_head, d_model) */
    atome_ternary_t Wk;   /* (d_head, d_model) */
    atome_ternary_t Wv;   /* (d_model, d_model) */
    uint16_t d_head;
    uint16_t top_k;
} atome_attn_t;

/* LayerNorm */
typedef struct {
    const float* gamma;   /* [d_model] */
    const float* beta;    /* [d_model] */
} atome_norm_t;

/* One Atome block */
typedef struct {
    atome_norm_t norm;
    atome_conv_t local_conv;
    atome_ssm_t ssm;
    atome_attn_t attn;
    atome_ternary_t router;  /* (n_pathways, d_model) */
} atome_block_t;

/* Full model */
typedef struct {
    atome_ternary_t embed;     /* (vocab, d_model) */
    atome_block_t blocks[ATOME_N_LAYERS];
    atome_norm_t final_norm;
    atome_ternary_t unembed;   /* (vocab, d_model) */
} atome_model_t;

/* ================================================================
 * Static inference buffers — NO heap allocation
 *
 * All pathway scratch arrays live here, NOT on the stack.
 * This avoids stack overflow on microcontrollers.
 * ================================================================ */

typedef struct {
    /* Token activations: (seq_len, d_model) */
    float x[ATOME_MAX_SEQ][ATOME_D_MODEL];
    /* Normalized input (shared across pathways) */
    float normed[ATOME_MAX_SEQ][ATOME_D_MODEL];
    /* Pathway output buffers (reused per block) */
    float path_local[ATOME_MAX_SEQ][ATOME_D_MODEL];
    float path_ssm[ATOME_MAX_SEQ][ATOME_D_MODEL];
    float path_attn[ATOME_MAX_SEQ][ATOME_D_MODEL];
    /* SSM hidden state — persistent across generation steps */
    float ssm_h[ATOME_N_LAYERS][ATOME_D_MODEL];
    /* Logits buffer */
    float logits[ATOME_VOCAB_SIZE];
    /* Per-token router weights */
    float router_w[ATOME_MAX_SEQ][ATOME_N_PATHWAYS];
    /* Attention scratch */
    float q[ATOME_D_HEAD];
    float k_cache[ATOME_MAX_SEQ][ATOME_D_HEAD];
    float v_cache[ATOME_MAX_SEQ][ATOME_D_MODEL];
    float attn_scores[ATOME_MAX_SEQ];
} atome_state_t;

/* ================================================================
 * Core operations
 * ================================================================ */

/*
 * Ternary matrix-vector multiply: out = scale * (W @ x)
 * W is packed ternary (rows x cols), x is float[cols], out is float[rows]
 *
 * THE hot path. Zero float multiplies. Pure add/sub/skip.
 */
void atome_ternary_matvec(
    const atome_ternary_t* W,
    const float* x,
    float* out
);

/*
 * Layer normalization (the ONLY float-heavy operation)
 */
void atome_layer_norm(
    float* x,          /* in-place, length = d_model */
    int dim,
    const atome_norm_t* params
);

/*
 * Causal depthwise conv1d with ternary kernel
 */
void atome_causal_conv(
    const float x[][ATOME_D_MODEL],
    int seq_len,
    const atome_conv_t* kernel,
    float out[][ATOME_D_MODEL]
);

/*
 * Diagonal SSM recurrent step
 */
void atome_ssm_forward(
    const float x[][ATOME_D_MODEL],
    int seq_len,
    const atome_ssm_t* params,
    float* h,          /* hidden state, persistent across calls */
    float out[][ATOME_D_MODEL]
);

/*
 * Sparse causal attention
 */
void atome_sparse_attn(
    const float x[][ATOME_D_MODEL],
    int seq_len,
    const atome_attn_t* params,
    atome_state_t* state,
    float out[][ATOME_D_MODEL]
);

/* ================================================================
 * High-level API
 * ================================================================ */

/*
 * Initialize inference state (zero buffers)
 */
void atome_init(atome_state_t* state);

/*
 * Load model from flat binary in flash/ROM
 * Returns 0 on success, -1 on error
 */
int atome_load(atome_model_t* model, const uint8_t* data, size_t len);

/*
 * Predict next token given a sequence
 * tokens: input token ids, length = n_tokens
 * Returns: predicted next token id (0-255)
 */
int atome_predict_next(
    const atome_model_t* model,
    atome_state_t* state,
    const int* tokens,
    int n_tokens
);

/*
 * Get logits for the last position (for external use)
 * Returns pointer to state->logits (ATOME_VOCAB_SIZE floats)
 */
const float* atome_get_logits(atome_state_t* state);

/*
 * Generate n_tokens of continuation
 * output: buffer to write generated token ids
 * Returns: number of tokens actually generated
 */
int atome_generate(
    const atome_model_t* model,
    atome_state_t* state,
    const int* prompt,
    int prompt_len,
    int* output,
    int max_tokens
);

/* ================================================================
 * Classification head (optional, for task-specific models)
 * ================================================================ */

#ifndef ATOME_MAX_CLASSES
#define ATOME_MAX_CLASSES   16
#endif

typedef struct {
    atome_model_t base;
    atome_ternary_t head;    /* (n_classes, d_model) */
    int n_classes;
} atome_classifier_t;

/*
 * Classify: run forward pass, then head on last hidden state.
 * Returns class index (argmax of head logits).
 * class_logits: if non-NULL, filled with raw logits (n_classes floats).
 */
int atome_classify(
    const atome_classifier_t* clf,
    atome_state_t* state,
    const int* tokens,
    int n_tokens,
    float* class_logits
);

/*
 * Load classifier from binary (ATOMECL magic)
 */
int atome_classifier_load(atome_classifier_t* clf, const uint8_t* data, size_t len);

/* ================================================================
 * Memory usage calculator (compile-time)
 * ================================================================ */

#define ATOME_STATE_SIZE   sizeof(atome_state_t)
/* Model weights are in flash, only state is in RAM */

#ifdef __cplusplus
}
#endif

#endif /* ATOME_H */

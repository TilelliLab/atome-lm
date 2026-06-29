/*
 * superesp_os.c — host-compilable SuperESP on-device "OS" dispatcher demo.
 *
 * Mirrors superesp/runtime/dispatcher.py in C: load the OS head + a sensor
 * head (same shared config, different ATOMECL01 blobs), run the OS head on a
 * fused telemetry token frame to get the device state, apply the
 * load-shedding policy, then dispatch the sensor frame to its head unless the
 * policy disabled it. Abstains when the top1-top2 margin is below threshold.
 *
 * This is the C reference the ESP-IDF firmware (superesp/firmware) follows.
 * Build (host):
 *   gcc -O2 -std=c99 -I<atome.h dir> -DATOME_*=... superesp_os.c <atome.c> -lm -o os
 *   ./os os_telem.atomecl <modality> sensor.atomecl "os toks" "sensor toks"
 *
 * OS class order MUST match superesp/datasets/os_telem.py CLASS_NAMES:
 *   0 normal  1 low_memory  2 overheating  3 wifi_degraded  4 power_fault
 */
#ifndef ATOME_D_MODEL
#define ATOME_D_MODEL    32
#endif
#ifndef ATOME_MAX_SEQ
#define ATOME_MAX_SEQ    32
#endif
#ifndef ATOME_N_LAYERS
#define ATOME_N_LAYERS   2
#endif
#ifndef ATOME_N_PATHWAYS
#define ATOME_N_PATHWAYS 3
#endif
#ifndef ATOME_VOCAB_SIZE
#define ATOME_VOCAB_SIZE 256
#endif
#ifndef ATOME_D_HEAD
#define ATOME_D_HEAD     8
#endif
#ifndef ATOME_KERNEL_SIZE
#define ATOME_KERNEL_SIZE 5
#endif
#ifndef ATOME_TOP_K
#define ATOME_TOP_K      4
#endif
#ifndef ATOME_MAX_CLASSES
#define ATOME_MAX_CLASSES 16
#endif

#include "atome.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define ABSTAIN_MARGIN 0.15f

static atome_classifier_t g_os, g_sensor;
static atome_state_t g_state;
/* The engine is zero-copy: a loaded classifier holds POINTERS into its blob
 * buffer (weights live in flash on-device). So each model needs its OWN
 * persistent buffer — sharing one buffer makes the second load silently
 * overwrite the first model's weights. */
static unsigned char g_blob_os[1 << 20];
static unsigned char g_blob_sensor[1 << 20];

/* OS state -> bitmask of disabled modalities. Modalities (demo subset):
 *   bit0 voice  bit1 sound_scene  bit2 motion  bit3 anomaly  */
static unsigned os_policy(int state) {
    switch (state) {
        case 1: /* low_memory */   return (1u<<0)|(1u<<1);
        case 2: /* overheating */  return (1u<<0)|(1u<<1);
        case 4: /* power_fault */  return (1u<<0)|(1u<<1)|(1u<<2)|(1u<<3);
        default: return 0u;        /* normal, wifi_degraded */
    }
}
static unsigned modality_bit(const char* m) {
    if (!strcmp(m,"voice")) return 1u<<0;
    if (!strcmp(m,"sound_scene")) return 1u<<1;
    if (!strcmp(m,"motion")) return 1u<<2;
    if (!strcmp(m,"anomaly")) return 1u<<3;
    return 0u;
}

static int parse_tokens(const char* s, int* out) {
    int n = 0; const char* p = s;
    while (*p && n < ATOME_MAX_SEQ) {
        char* e; long v = strtol(p, &e, 10);
        if (e == p) break;
        out[n++] = (int)v; p = e;
    }
    return n;
}

static int load_blob(atome_classifier_t* clf, const char* path,
                     unsigned char* buf, size_t bufsz) {
    FILE* f = fopen(path, "rb");
    if (!f) return -1;
    size_t n = fread(buf, 1, bufsz, f);
    fclose(f);
    return atome_classifier_load(clf, buf, n);  /* clf points INTO buf */
}

/* classify; returns class idx, writes margin (top1-top2 of softmax-free logits
 * normalized) into *margin via a simple softmax. */
static int classify_with_margin(atome_classifier_t* clf, int* toks, int n, float* margin) {
    float logits[ATOME_MAX_CLASSES];
    int cls = atome_classify(clf, &g_state, toks, n, logits);
    /* softmax margin */
    int k = clf->n_classes;
    float mx = logits[0];
    for (int i=1;i<k;i++) if (logits[i]>mx) mx=logits[i];
    float sum=0, top1=0, top2=0;
    for (int i=0;i<k;i++){ float e=expf(logits[i]-mx); sum+=e; }
    for (int i=0;i<k;i++){ float p=expf(logits[i]-mx)/sum; if(p>top1){top2=top1;top1=p;} else if(p>top2)top2=p; }
    *margin = top1 - top2;
    return cls;
}

int main(int argc, char** argv) {
    if (argc < 6) {
        fprintf(stderr, "usage: %s os.atomecl sensor_modality sensor.atomecl \"os toks\" \"sensor toks\"\n", argv[0]);
        return 2;
    }
    const char* os_path = argv[1];
    const char* modality = argv[2];
    const char* sensor_path = argv[3];

    if (load_blob(&g_os, os_path, g_blob_os, sizeof(g_blob_os)) != 0) {
        fprintf(stderr,"load os failed\n"); return 2; }
    if (load_blob(&g_sensor, sensor_path, g_blob_sensor, sizeof(g_blob_sensor)) != 0) {
        fprintf(stderr,"load sensor failed\n"); return 2; }

    int os_toks[ATOME_MAX_SEQ], se_toks[ATOME_MAX_SEQ];
    int n_os = parse_tokens(argv[4], os_toks);
    int n_se = parse_tokens(argv[5], se_toks);

    atome_init(&g_state);
    float m_os; int state = classify_with_margin(&g_os, os_toks, n_os, &m_os);
    unsigned disabled = os_policy(state);
    printf("os_state=%d margin=%.3f disabled_mask=0x%x\n", state, m_os, disabled);

    if (disabled & modality_bit(modality)) {
        printf("sensor=%s DISABLED_BY_POLICY\n", modality);
        return 0;
    }
    float m_se; int cls = classify_with_margin(&g_sensor, se_toks, n_se, &m_se);
    if (m_se < ABSTAIN_MARGIN) printf("sensor=%s ABSTAIN margin=%.3f\n", modality, m_se);
    else printf("sensor=%s class=%d margin=%.3f\n", modality, cls, m_se);
    return 0;
}

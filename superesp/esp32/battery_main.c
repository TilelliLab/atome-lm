/*
 * battery_main.c — SuperESP on-device application test battery.
 *
 * Runs ALL SuperESP heads one after another from a single firmware: verifies
 * each baked ATOMECL01 blob's integrity (FNV-1a-64, computed identically on the
 * host in gen_battery.py), then loads it, times one classification, and prints
 * a machine-parseable report over serial. The host grades each line vs golden.
 *
 * Platform-agnostic: compiles for QEMU Cortex-M3 (main()) and ESP-IDF (app_main()).
 * On ESP32 it also reports per-head latency (US) and free heap (HEAP).
 *
 * Report line per head:
 *   HEAD <name> CLASS <got> EXPECT <want> <PASS|FAIL> [US <microsec>] [HEAP <kb>]
 *   HEAD <name> INTEG_FAIL                         (blob checksum mismatch)
 * framed by:  SUPERESP BATTERY START / SUPERESP BATTERY DONE pass=<n>/<N>
 */
#include "atome.h"
#include "battery_data.h"
#include <stdio.h>
#include <stdint.h>

#ifdef ESP_PLATFORM
#include "esp_system.h"     /* esp_get_free_heap_size */
#include "esp_heap_caps.h"
#include "esp_timer.h"      /* esp_timer_get_time */
#endif

static atome_classifier_t g_clf;
static atome_state_t g_state;

/* FNV-1a 64-bit — load-time integrity (catches flash bit-rot / wrong blob).
 * Identical to gen_battery.py's _fnv1a64 so the baked value must match. */
static uint64_t fnv1a64(const unsigned char* p, unsigned int n) {
    uint64_t h = 0xcbf29ce484222325ULL;
    for (unsigned int i = 0; i < n; ++i) { h ^= p[i]; h *= 0x100000001b3ULL; }
    return h;
}

static int run_battery(void) {
    int pass = 0;
    printf("SUPERESP BATTERY START n=%d\n", N_HEADS);
    for (int i = 0; i < N_HEADS; ++i) {
        if (fnv1a64(head_blobs[i], head_blob_lens[i]) != head_fnv[i]) {
            printf("HEAD %s INTEG_FAIL\n", head_names[i]);   /* refuse a corrupt blob */
            continue;
        }
        if (atome_classifier_load(&g_clf, head_blobs[i], head_blob_lens[i]) != 0) {
            printf("HEAD %s LOAD_FAIL\n", head_names[i]);
            continue;
        }
        atome_init(&g_state);
        float logits[ATOME_MAX_CLASSES];
#ifdef ESP_PLATFORM
        int64_t t0 = esp_timer_get_time();
        int got = atome_classify(&g_clf, &g_state, head_toks[i], head_ntoks[i], logits);
        long us = (long)(esp_timer_get_time() - t0);
#else
        int got = atome_classify(&g_clf, &g_state, head_toks[i], head_ntoks[i], logits);
#endif
        int want = head_expect[i];
        int ok = (got == want);
        pass += ok;
#ifdef ESP_PLATFORM
        printf("HEAD %s CLASS %d EXPECT %d %s US %ld HEAP %u\n", head_names[i], got, want,
               ok ? "PASS" : "FAIL", us, (unsigned)(esp_get_free_heap_size() / 1024));
#else
        printf("HEAD %s CLASS %d EXPECT %d %s\n", head_names[i], got, want, ok ? "PASS" : "FAIL");
#endif
    }
    printf("SUPERESP BATTERY DONE pass=%d/%d\n", pass, N_HEADS);
    return pass;
}

#ifdef ESP_PLATFORM
void app_main(void) {
    printf("\n==================== SUPERESP on SILICON ====================\n");
    printf("heads=%d  state=%u B  free heap=%u KB  integrity=FNV1a64\n", N_HEADS,
           (unsigned)sizeof(atome_state_t), (unsigned)(esp_get_free_heap_size() / 1024));
    int64_t t0 = esp_timer_get_time();
    run_battery();
    printf("battery wall-time: %lld ms\n", (long long)((esp_timer_get_time() - t0) / 1000));
}
#else
void _init(void) {}
void _fini(void) {}
int main(void) { return run_battery() == N_HEADS ? 0 : 1; }
#endif

/*
 * superesp_main.c — SuperESP on-device "OS" firmware (ESP32 / ESP-IDF).
 *
 * BUILD-ONLY SKELETON. Requires ESP-IDF + a board; not flashed/measured here.
 * Reuses the vendored Atome engine (atome.c/.h) and an embedded ATOMECL01 head.
 *
 * Boot flow:
 *   1. gather ESP32 telemetry  -> OS fused frame (floats)
 *   2. quantize to bytes (vmin/vmax baked from os_telem.tok.json)
 *   3. atome_classify(OS head) -> device state + load-shedding policy
 *   4. read active sensor -> dispatch to its head (abstain if unsure)
 *
 * Compile-time config (main/CMakeLists.txt) MUST match the SuperESP shared
 * config the blobs were exported with: d_model=32 n_layers=2 d_head=8.
 */
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "esp_chip_info.h"
#include "driver/adc.h"

#include "atome.h"

/* Embedded OS head blob (see main/CMakeLists.txt EMBED_FILES). */
extern const uint8_t os_head_start[] asm("_binary_os_telem_atomecl_start");
extern const uint8_t os_head_end[]   asm("_binary_os_telem_atomecl_end");

static atome_classifier_t g_os;
static atome_state_t       g_state;

/* OS head feature order (superesp/datasets/os_telem.py, time-major 4x8 = 32):
 * [heap,temp,rssi,vbat,latency,adc_noise,task_q,brownout] x 4 timesteps.
 * vmin/vmax are placeholders here; the build script bakes the real constants
 * from os_telem.tok.json. */
static const float VMIN[32] = {0};   /* filled by codegen from tok.json */
static const float VMAX[32] = {0};

static const char* OS_STATES[5] =
    {"normal","low_memory","overheating","wifi_degraded","power_fault"};

static int quantize(float v, float lo, float hi) {
    if (hi <= lo) return 0;
    float n = (v - lo) / (hi - lo);
    if (n < 0) n = 0; if (n > 1) n = 1;
    return (int)(n * 255.0f + 0.5f);
}

/* Gather one OS telemetry timestep into 8 floats. */
static void read_os_step(float* out8) {
    out8[0] = (float)esp_get_free_heap_size() / 1024.0f;     /* heap_kb */
    out8[1] = 45.0f;   /* TODO: temperature_sensor_get_celsius() */
    out8[2] = -55.0f;  /* TODO: esp_wifi_sta_get_rssi() */
    out8[3] = 3300.0f; /* TODO: adc battery divider */
    out8[4] = 8.0f;    /* TODO: measured loop latency ms */
    out8[5] = 2.0f;    /* TODO: adc noise estimate */
    out8[6] = 1.0f;    /* TODO: uxQueueMessagesWaiting */
    out8[7] = 0.0f;    /* TODO: brownout flag */
}

void app_main(void) {
    if (atome_classifier_load(&g_os, os_head_start,
                              (size_t)(os_head_end - os_head_start)) != 0) {
        printf("SuperESP: OS head load failed\n");
        return;
    }
    printf("SuperESP OS up: %d classes, free heap %u\n",
           g_os.n_classes, (unsigned)esp_get_free_heap_size());

    while (1) {
        /* Build the 4-timestep fused frame. */
        float frame[32];
        for (int t = 0; t < 4; ++t) read_os_step(&frame[t * 8]);

        int toks[32];
        for (int i = 0; i < 32; ++i) toks[i] = quantize(frame[i], VMIN[i], VMAX[i]);

        atome_init(&g_state);
        float logits[ATOME_MAX_CLASSES];
        int state = atome_classify(&g_os, &g_state, toks, 32, logits);
        printf("SuperESP device_state=%s\n",
               (state >= 0 && state < 5) ? OS_STATES[state] : "?");

        /* TODO: apply policy, then read active sensor + dispatch to its head. */
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}

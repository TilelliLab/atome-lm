/*
 * Atome on ESP32 — production prototype
 * ------------------------------------------------------------------
 * Boots, prints chip/flash/PSRAM facts, loads the embedded Atome model
 * from flash, runs a real on-silicon benchmark (tokens/sec, ms/token,
 * RAM high-water), then drops into an offline text-generation REPL over
 * USB serial. No network, no cloud — generation runs entirely on-chip.
 *
 * The model weights live in flash (rodata, embedded blob). The big
 * inference state (atome_state_t) is placed in PSRAM when present.
 *
 * NOTE: build config (d_model/n_layers/...) is set in main/CMakeLists.txt
 * via compile definitions and MUST match the embedded checkpoint.
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_system.h"
#include "driver/uart.h"
/* The UART VFS helper was renamed between ESP-IDF versions; bind whichever exists. */
#if defined(__has_include)
#  if __has_include("driver/uart_vfs.h")
#    include "driver/uart_vfs.h"
#    define ATOME_UART_USE_DRIVER(n) uart_vfs_dev_use_driver(n)
#  elif __has_include("esp_vfs_dev.h")
#    include "esp_vfs_dev.h"
#    define ATOME_UART_USE_DRIVER(n) esp_vfs_dev_uart_use_driver(n)
#  endif
#endif
#ifndef ATOME_UART_USE_DRIVER
#  define ATOME_UART_USE_DRIVER(n) ((void)0)
#endif
#if CONFIG_SPIRAM
#include "esp_psram.h"
#endif

#include "atome.h"

/* Embedded model blob (see main/CMakeLists.txt EMBED_FILES) */
extern const uint8_t model_start[] asm("_binary_model_atome_start");
extern const uint8_t model_end[]   asm("_binary_model_atome_end");

static atome_model_t  model;
static atome_state_t *state;          /* allocated in PSRAM */

/* Short prompts: leave maximum budget for generation within the seq window
 * (the wroom profile is only seq=24, so prompt+output must fit in 24 bytes). */
static const char *PROMPTS[] = {
    "Once",
    "The dog",
    "A girl",
};

/* ---- printable byte helper -------------------------------------- */
static void put_token(int c) {
    putchar((c >= 32 && c < 127) || c == '\n' ? c : '.');
}

/* ---- generate + print, return tokens/sec ------------------------ */
static double generate_and_print(const char *prompt, int n_gen) {
    int toks[ATOME_MAX_SEQ];
    int out[ATOME_MAX_SEQ];
    int pl = (int)strlen(prompt);
    if (pl > ATOME_MAX_SEQ - 1) pl = ATOME_MAX_SEQ - 1;
    if (n_gen > ATOME_MAX_SEQ - pl) n_gen = ATOME_MAX_SEQ - pl;
    for (int i = 0; i < pl; i++) toks[i] = (uint8_t)prompt[i];

    atome_init(state);
    int64_t t0 = esp_timer_get_time();
    int g = atome_generate(&model, state, toks, pl, out, n_gen);
    int64_t t1 = esp_timer_get_time();

    double secs = (t1 - t0) / 1e6;
    double tps  = g > 0 ? g / secs : 0.0;

    printf("\nprompt: %s\n>>> ", prompt);
    for (int i = 0; i < g; i++) put_token(out[i]);
    printf("\n  %d tok in %.1f ms  =  %.1f tok/s  (%.2f ms/tok)\n",
           g, secs * 1000.0, tps, g > 0 ? secs * 1000.0 / g : 0.0);
    return tps;
}

/* ---- hardware facts --------------------------------------------- */
static void print_facts(void) {
    esp_chip_info_t info;
    esp_chip_info(&info);
    uint32_t flash_sz = 0;
    esp_flash_get_size(NULL, &flash_sz);

    const char *chip = "ESP32?";
    switch (info.model) {
        case CHIP_ESP32:   chip = "ESP32";    break;
        case CHIP_ESP32S2: chip = "ESP32-S2"; break;
        case CHIP_ESP32S3: chip = "ESP32-S3"; break;
        case CHIP_ESP32C3: chip = "ESP32-C3"; break;
        case CHIP_ESP32C6: chip = "ESP32-C6"; break;
        case CHIP_ESP32H2: chip = "ESP32-H2"; break;
        default: break;
    }
    printf("\n==================== ATOME on SILICON ====================\n");
    printf("chip      : %s  rev v%d.%d  cores=%d\n",
           chip, info.revision / 100, info.revision % 100, info.cores);
    printf("flash     : %lu MB\n", (unsigned long)(flash_sz / (1024 * 1024)));

    size_t psram = 0;
#if CONFIG_SPIRAM
    psram = esp_psram_get_size();
#endif
    printf("PSRAM     : %u KB %s\n", (unsigned)(psram / 1024),
           psram ? "(detected)" : "(NONE — see note below)");
    printf("free heap : %u KB internal (largest block %u KB)\n",
           (unsigned)(heap_caps_get_free_size(MALLOC_CAP_INTERNAL) / 1024),
           (unsigned)(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL) / 1024));
    printf("model     : %u bytes embedded in flash\n",
           (unsigned)(model_end - model_start));
    printf("config    : d=%d layers=%d head=%d seq=%d  state=%u KB\n",
           ATOME_D_MODEL, ATOME_N_LAYERS, ATOME_D_HEAD, ATOME_MAX_SEQ,
           (unsigned)(sizeof(atome_state_t) / 1024));
    printf("==========================================================\n");
}

/* ---- allocate inference state (PSRAM first, then internal) ------ */
static int alloc_state(void) {
    state = heap_caps_malloc(sizeof(atome_state_t), MALLOC_CAP_SPIRAM);
    if (state) { printf("[state] %u KB in PSRAM\n",
                        (unsigned)(sizeof(atome_state_t) / 1024)); return 0; }
    state = heap_caps_malloc(sizeof(atome_state_t), MALLOC_CAP_INTERNAL);
    if (state) { printf("[state] %u KB in internal SRAM\n",
                        (unsigned)(sizeof(atome_state_t) / 1024)); return 0; }

    printf("\n*** ERROR: could not allocate %u KB for inference state.\n",
           (unsigned)(sizeof(atome_state_t) / 1024));
    printf("*** largest contiguous internal block is only %u KB.\n",
           (unsigned)(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL) / 1024));
    printf("*** Tell me this number — I'll rebuild at a context length that fits\n");
    printf("*** (seq32=209KB, seq24=159KB, seq16=109KB), or use: ./atome.sh build toy\n");
    return -1;
}

/* ---- interactive REPL over UART stdin --------------------------- */
static void repl(void) {
    /* line-buffered stdin on UART0 (the USB-serial console) */
    setvbuf(stdin, NULL, _IONBF, 0);
    uart_driver_install(UART_NUM_0, 256, 0, 0, NULL, 0);
    ATOME_UART_USE_DRIVER(UART_NUM_0);

    printf("\n--- REPL: type a prompt, press Enter. Ctrl-] to quit monitor. ---\n");
    char line[160];
    while (1) {
        printf("\natome> ");
        fflush(stdout);
        if (!fgets(line, sizeof(line), stdin)) { vTaskDelay(pdMS_TO_TICKS(50)); continue; }
        size_t n = strlen(line);
        while (n && (line[n-1] == '\n' || line[n-1] == '\r')) line[--n] = 0;
        if (n == 0) continue;
        generate_and_print(line, ATOME_MAX_SEQ - (int)n - 1);
    }
}

void app_main(void) {
    print_facts();

    if (atome_load(&model, model_start, (size_t)(model_end - model_start)) != 0) {
        printf("*** ERROR: atome_load failed (config/checkpoint mismatch?)\n");
        return;
    }
    if (alloc_state() != 0) return;

    /* On-silicon benchmark — guaranteed visible result, no typing needed */
    printf("\n--- benchmark (greedy, offline) ---\n");
    double sum = 0; int k = sizeof(PROMPTS) / sizeof(PROMPTS[0]);
    for (int i = 0; i < k; i++) sum += generate_and_print(PROMPTS[i], 48);
    printf("\naverage: %.1f tok/s   |   heap low-water: %u KB internal\n",
           sum / k, (unsigned)(heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL) / 1024));

    repl();
}

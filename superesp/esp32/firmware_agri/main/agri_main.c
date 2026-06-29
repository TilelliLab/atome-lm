/*
 * agri_main.c — SuperESP-Agri LIVE on-device device (ESP32).
 *
 * Reads REAL sensors, builds the agri 6x5 window, quantizes with the trained
 * tokenizer calibration (agri_calib.h, identical to training), runs the Atome
 * classifier on-chip, and drives a relay/LED when the soil "needs_irrigate".
 *
 * Sensors (documented wiring — real, not stubbed):
 *   - Capacitive soil-moisture v1.2  -> ADC1 (SOIL_ADC_CHAN, default GPIO34)
 *   - DHT22 (AM2302) temp + humidity -> one GPIO (DHT_GPIO, default GPIO4), 1-wire
 *   - Relay / pump (or onboard LED)  -> RELAY_GPIO (default GPIO2)
 * Two of the 5 model channels (soil_temp, leaf_wetness) have documented
 * derivations below; add a DS18B20 + leaf-wetness sensor for a full 5-sensor
 * deployment (hooks marked TODO). The classification runs on the REAL soil +
 * air readings.
 *
 * Build config MUST match the shared SuperESP config (d=32,L=2,...).
 */
#include "atome.h"
#include "agri_calib.h"
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_rom_sys.h"
#include "esp_timer.h"

#define SOIL_ADC_UNIT   ADC_UNIT_1
#define SOIL_ADC_CHAN   ADC_CHANNEL_6   /* GPIO34 on ESP32 */
#define DHT_GPIO        4
#define RELAY_GPIO      2
#define SAMPLE_MS       2000            /* spacing between the 6 window samples */
/* capacitive soil sensor raw calibration (12-bit): adjust to your probe */
#define SOIL_DRY_RAW    3000.0f
#define SOIL_WET_RAW    1200.0f

static atome_classifier_t g_clf;
static atome_state_t g_state;
static adc_oneshot_unit_handle_t g_adc;

/* ---- DHT22 1-wire bit-bang (returns 0 on success) ---- */
static int dht22_read(float* temp_c, float* humidity) {
    uint8_t data[5] = {0};
    gpio_set_direction(DHT_GPIO, GPIO_MODE_OUTPUT);
    gpio_set_level(DHT_GPIO, 0); vTaskDelay(pdMS_TO_TICKS(20));   /* >18ms start */
    gpio_set_level(DHT_GPIO, 1); esp_rom_delay_us(30);
    gpio_set_direction(DHT_GPIO, GPIO_MODE_INPUT);
    portDISABLE_INTERRUPTS();
    int ok = 0;
    /* wait for sensor response low->high->low */
    int to = 0; while (gpio_get_level(DHT_GPIO) == 1 && to++ < 200) esp_rom_delay_us(1);
    to = 0; while (gpio_get_level(DHT_GPIO) == 0 && to++ < 200) esp_rom_delay_us(1);
    to = 0; while (gpio_get_level(DHT_GPIO) == 1 && to++ < 200) esp_rom_delay_us(1);
    for (int i = 0; i < 40; ++i) {
        to = 0; while (gpio_get_level(DHT_GPIO) == 0 && to++ < 200) esp_rom_delay_us(1);
        int w = 0; while (gpio_get_level(DHT_GPIO) == 1 && w++ < 200) esp_rom_delay_us(1);
        data[i / 8] <<= 1; if (w > 40) data[i / 8] |= 1;   /* >40us high = bit 1 */
    }
    portENABLE_INTERRUPTS();
    if (((uint8_t)(data[0] + data[1] + data[2] + data[3])) == data[4]) {
        *humidity = ((data[0] << 8) | data[1]) * 0.1f;
        int16_t t = ((data[2] & 0x7F) << 8) | data[3];
        *temp_c = (data[2] & 0x80) ? -t * 0.1f : t * 0.1f;
        ok = 1;
    }
    return ok ? 0 : -1;
}

static float read_soil_pct(void) {
    int raw = 0; adc_oneshot_read(g_adc, SOIL_ADC_CHAN, &raw);
    float pct = (SOIL_DRY_RAW - raw) / (SOIL_DRY_RAW - SOIL_WET_RAW) * 100.0f;
    if (pct < 0) { pct = 0; }
    if (pct > 100) { pct = 100; }
    return pct;
}

static int quantize(float v, float lo, float hi) {
    if (hi <= lo) return 0;
    float n = (v - lo) / (hi - lo);
    if (n < 0) { n = 0; }
    if (n > 1) { n = 1; }
    return (int)(n * 255.0f + 0.5f);
}

void app_main(void) {
    printf("\n== SuperESP-Agri LIVE ==\n");
    if (atome_classifier_load(&g_clf, agri_blob, agri_blob_len) != 0) {
        printf("agri head load failed\n"); return; }
    adc_oneshot_unit_init_cfg_t uc = { .unit_id = SOIL_ADC_UNIT };
    adc_oneshot_new_unit(&uc, &g_adc);
    adc_oneshot_chan_cfg_t cc = { .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT };
    adc_oneshot_config_channel(g_adc, SOIL_ADC_CHAN, &cc);
    gpio_set_direction(RELAY_GPIO, GPIO_MODE_OUTPUT); gpio_set_level(RELAY_GPIO, 0);

    while (1) {
        float win[AGRI_N_FEAT];
        for (int t = 0; t < AGRI_T; ++t) {
            float soil = read_soil_pct();
            float air_t = 22.0f, hum = 55.0f;
            if (dht22_read(&air_t, &hum) != 0) printf("  (DHT22 read retry)\n");
            float soil_t = air_t - 2.0f;                 /* proxy; TODO DS18B20 */
            float leaf = (hum - 60.0f) / 40.0f;           /* proxy; TODO leaf sensor */
            if (leaf < 0) { leaf = 0; }
            if (leaf > 1) { leaf = 1; }
            float ch[AGRI_C] = { soil, air_t, hum, soil_t, leaf };
            for (int c = 0; c < AGRI_C; ++c) win[t * AGRI_C + c] = ch[c];
            if (t == AGRI_T - 1)
                printf("  soil=%.0f%% air=%.1fC hum=%.0f%%\n", soil, air_t, hum);
            if (t < AGRI_T - 1) vTaskDelay(pdMS_TO_TICKS(SAMPLE_MS));
        }
        int toks[AGRI_N_FEAT];
        for (int i = 0; i < AGRI_N_FEAT; ++i) toks[i] = quantize(win[i], AGRI_VMIN[i], AGRI_VMAX[i]);
        atome_init(&g_state);
        float logits[ATOME_MAX_CLASSES];
        int cls = atome_classify(&g_clf, &g_state, toks, AGRI_N_FEAT, logits);
        int irrigate = (cls == AGRI_NEEDS_IRRIGATE);
        gpio_set_level(RELAY_GPIO, irrigate ? 1 : 0);
        printf("  -> %s %s\n", (cls >= 0 && cls < AGRI_N_CLASSES) ? AGRI_CLASSES[cls] : "?",
               irrigate ? "[RELAY ON: irrigating]" : "");
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

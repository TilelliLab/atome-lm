/*
 * logger_main.c — SuperESP DATA-LOGGER firmware (ESP32).
 *
 * Reads the same real sensors as the agri device (capacitive soil-moisture ADC +
 * DHT22 temp/humidity), builds one 6x5 (=30) feature frame, and streams it over
 * serial as a CSV line:   CSV,<f0>,<f1>,...,<f29>
 * No classification — this is the "record mode" that lets a user collect their
 * OWN labelled data. On the host:  `superesp log --label <state> --out my.csv`
 * captures these lines, appends the label column, and produces a training CSV.
 *
 * Wiring identical to firmware_agri (soil->GPIO34/ADC1_CH6, DHT22->GPIO4).
 */
#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_rom_sys.h"

#define SOIL_ADC_UNIT  ADC_UNIT_1
#define SOIL_ADC_CHAN  ADC_CHANNEL_6   /* GPIO34 */
#define DHT_GPIO       4
#define SAMPLE_MS      1000            /* spacing of the 6 sub-samples */
#define FRAME_MS       3000            /* spacing between CSV frames */
#define SOIL_DRY_RAW   3000.0f
#define SOIL_WET_RAW   1200.0f
#define T 6
#define C 5

static adc_oneshot_unit_handle_t g_adc;

static int dht22_read(float* temp_c, float* humidity) {
    uint8_t data[5] = {0};
    gpio_set_direction(DHT_GPIO, GPIO_MODE_OUTPUT);
    gpio_set_level(DHT_GPIO, 0); vTaskDelay(pdMS_TO_TICKS(20));
    gpio_set_level(DHT_GPIO, 1); esp_rom_delay_us(30);
    gpio_set_direction(DHT_GPIO, GPIO_MODE_INPUT);
    portDISABLE_INTERRUPTS();
    int to = 0; while (gpio_get_level(DHT_GPIO) == 1 && to++ < 200) esp_rom_delay_us(1);
    to = 0; while (gpio_get_level(DHT_GPIO) == 0 && to++ < 200) esp_rom_delay_us(1);
    to = 0; while (gpio_get_level(DHT_GPIO) == 1 && to++ < 200) esp_rom_delay_us(1);
    for (int i = 0; i < 40; ++i) {
        to = 0; while (gpio_get_level(DHT_GPIO) == 0 && to++ < 200) esp_rom_delay_us(1);
        int w = 0; while (gpio_get_level(DHT_GPIO) == 1 && w++ < 200) esp_rom_delay_us(1);
        data[i / 8] <<= 1; if (w > 40) data[i / 8] |= 1;
    }
    portENABLE_INTERRUPTS();
    if (((uint8_t)(data[0] + data[1] + data[2] + data[3])) == data[4]) {
        *humidity = ((data[0] << 8) | data[1]) * 0.1f;
        int16_t t = ((data[2] & 0x7F) << 8) | data[3];
        *temp_c = (data[2] & 0x80) ? -t * 0.1f : t * 0.1f;
        return 0;
    }
    return -1;
}

static float read_soil_pct(void) {
    int raw = 0; adc_oneshot_read(g_adc, SOIL_ADC_CHAN, &raw);
    float pct = (SOIL_DRY_RAW - raw) / (SOIL_DRY_RAW - SOIL_WET_RAW) * 100.0f;
    if (pct < 0) { pct = 0; }
    if (pct > 100) { pct = 100; }
    return pct;
}

void app_main(void) {
    adc_oneshot_unit_init_cfg_t uc = { .unit_id = SOIL_ADC_UNIT };
    adc_oneshot_new_unit(&uc, &g_adc);
    adc_oneshot_chan_cfg_t cc = { .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT };
    adc_oneshot_config_channel(g_adc, SOIL_ADC_CHAN, &cc);

    printf("SUPERESP LOGGER (agri 6x5 frame). Lines: CSV,<30 floats>\n");
    /* header for humans / tooling */
    printf("CSV_HEADER");
    for (int t = 0; t < T; ++t) {
        const char* ch[C] = {"soil", "airT", "hum", "soilT", "leaf"};
        for (int c = 0; c < C; ++c) printf(",t%d_%s", t, ch[c]);
    }
    printf("\n");

    while (1) {
        float win[T * C];
        for (int t = 0; t < T; ++t) {
            float soil = read_soil_pct();
            float air_t = 22.0f, hum = 55.0f;
            dht22_read(&air_t, &hum);
            float soil_t = air_t - 2.0f;
            float leaf = (hum - 60.0f) / 40.0f;
            if (leaf < 0) { leaf = 0; }
            if (leaf > 1) { leaf = 1; }
            float vals[C] = { soil, air_t, hum, soil_t, leaf };
            for (int c = 0; c < C; ++c) win[t * C + c] = vals[c];
            if (t < T - 1) vTaskDelay(pdMS_TO_TICKS(SAMPLE_MS));
        }
        printf("CSV");
        for (int i = 0; i < T * C; ++i) printf(",%.3f", win[i]);
        printf("\n");
        vTaskDelay(pdMS_TO_TICKS(FRAME_MS));
    }
}

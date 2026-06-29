"""superesp.datasets.os_telem — SuperESP-OS: SYNTH device-health telemetry.

The "OS" head reads the ESP32's OWN telemetry (the info the runtime gathers
from the chip) and classifies device state. This is the head that makes Atome
the on-device supervisor — see superesp/runtime/.

A snapshot window of 8 device signals x 4 steps (time-major) = 32:
    [free_heap_kb, cpu_temp_C, wifi_rssi_dbm, vbat_mV, loop_latency_ms,
     adc_noise, task_queue_depth, brownout_flag]
Classes:
    normal        — healthy device
    low_memory    — heap fragmenting/leaking toward 0
    overheating    — cpu_temp climbing
    wifi_degraded — RSSI collapsing, latency rising
    power_fault   — vbat sagging + brownout flag

SYNTH — these are exactly the fields an ESP-IDF firmware exposes
(esp_get_free_heap_size, temperature_sensor, esp_wifi rssi, adc, etc.).
"""
from __future__ import annotations

import numpy as np

from superesp.datasets import Dataset, make_splits

CLASS_NAMES = ["normal", "low_memory", "overheating", "wifi_degraded", "power_fault"]
SIGNALS = ["free_heap_kb", "cpu_temp_C", "wifi_rssi_dbm", "vbat_mV",
           "loop_latency_ms", "adc_noise", "task_q_depth", "brownout_flag"]
T = 4
C = 8


def _window(rng, kind: str) -> np.ndarray:
    heap = np.full(T, 180.0); temp = np.full(T, 45.0); rssi = np.full(T, -55.0)
    vbat = np.full(T, 3300.0); lat = np.full(T, 8.0); noise = np.full(T, 2.0)
    q = np.full(T, 1.0); brown = np.full(T, 0.0)
    if kind == "normal":
        heap += rng.normal(0, 8, T); temp += rng.normal(0, 1.5, T); rssi += rng.normal(0, 3, T)
        vbat += rng.normal(0, 15, T); lat += rng.normal(0, 1, T); noise += rng.normal(0, 0.5, T)
        q += rng.poisson(1, T)
    elif kind == "low_memory":
        heap = np.linspace(rng.uniform(60, 90), rng.uniform(5, 20), T) + rng.normal(0, 3, T)
        lat = np.linspace(10, rng.uniform(20, 40), T) + rng.normal(0, 2, T)
        temp += rng.normal(0, 1.5, T); rssi += rng.normal(0, 3, T); vbat += rng.normal(0, 15, T)
        q += rng.poisson(4, T)
    elif kind == "overheating":
        temp = np.linspace(rng.uniform(55, 65), rng.uniform(80, 95), T) + rng.normal(0, 1.5, T)
        heap += rng.normal(0, 8, T); rssi += rng.normal(0, 3, T)
        lat += rng.normal(2, 1, T); noise += rng.normal(1, 0.5, T); q += rng.poisson(1, T)
    elif kind == "wifi_degraded":
        rssi = np.linspace(rng.uniform(-78, -70), rng.uniform(-95, -88), T) + rng.normal(0, 2, T)
        lat = np.linspace(15, rng.uniform(60, 120), T) + rng.normal(0, 5, T)
        heap += rng.normal(0, 8, T); temp += rng.normal(0, 1.5, T); q += rng.poisson(3, T)
    elif kind == "power_fault":
        vbat = np.linspace(rng.uniform(3100, 3200), rng.uniform(2700, 2950), T) + rng.normal(0, 20, T)
        brown = np.array([0, 0, rng.integers(0, 2), 1], dtype=float)
        noise += rng.normal(2, 1, T); lat += rng.normal(3, 2, T)
        heap += rng.normal(0, 8, T); temp += rng.normal(0, 1.5, T); rssi += rng.normal(0, 3, T)
    return np.stack([heap, temp, rssi, vbat, lat, noise, q, brown], axis=1)


def load(n_per_class: int = 600, seed: int = 0, noise_frac: float = 0.65) -> Dataset:
    rng = np.random.default_rng(seed)
    X, y = [], []
    for ci, kind in enumerate(CLASS_NAMES):
        for _ in range(n_per_class):
            X.append(_window(rng, kind).reshape(-1))
            y.append(ci)
    X = np.asarray(X)
    X = X + rng.normal(0, 1, X.shape) * X.std(0, keepdims=True) * noise_frac
    return make_splits("os_telem", "SYNTH", CLASS_NAMES, X, np.asarray(y),
                       seed=seed, description="4-step x 8 ESP32 telemetry signals",
                       stream_shape=(T, C))

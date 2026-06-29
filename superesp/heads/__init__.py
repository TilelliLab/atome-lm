"""superesp.heads — the 7 SuperESP prototype heads.

Each head = (name, human title, dataset loader). All share the same Atome
architecture (config.SHARED); only the trained weights + n_classes differ, so
the C engine compiles once and loads any head's ATOMECL01 blob.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from superesp.datasets import (
    agri, voice, motion, sound_scene, anomaly, air, os_telem,
    power, occupancy, wearable, water, forecast, Dataset,
)


@dataclass(frozen=True)
class Head:
    name: str
    title: str
    loader: Callable[..., Dataset]
    blurb: str


HEADS: list[Head] = [
    Head("agri", "SuperESP-Agri", agri.load,
         "soil/climate stream -> irrigate / frost / pest / healthy / fault"),
    Head("voice", "SuperESP-Voice", voice.load,
         "I2S mic -> farm voice commands (on/off/stop/go)"),
    Head("motion", "SuperESP-Motion", motion.load,
         "IMU stream -> activity / gesture / fall"),
    Head("sound_scene", "SuperESP-Sound-Scene", sound_scene.load,
         "ambient audio -> acoustic event (alarm/break/speech/quiet)"),
    Head("anomaly", "SuperESP-Anomaly", anomaly.load,
         "vibration -> machine health (normal/imbalance/bearing/looseness)"),
    Head("air", "SuperESP-Air", air.load,
         "gas+climate -> air quality / leak (clean/co2/gas/smoke)"),
    Head("os_telem", "SuperESP-OS", os_telem.load,
         "fused ESP32 telemetry -> device state (the on-device OS head)"),
    Head("power", "SuperESP-Power", power.load,
         "CT-clamp energy/NILM -> load type (off/resistive/motor/electronic)"),
    Head("occupancy", "SuperESP-Occupancy", occupancy.load,
         "PIR+CO2+sound -> room occupancy (empty/occupied/crowded)"),
    Head("wearable", "SuperESP-Wearable", wearable.load,
         "PPG+IMU -> heart/activity state (rest/active/exercise/irregular)"),
    Head("water", "SuperESP-Water", water.load,
         "flow+pressure+moisture -> leak/flood (no_flow/normal/leak/burst)"),
    Head("forecast", "SuperESP-Forecast", forecast.load,
         "degradation window -> time-to-failure bucket (safe/later/soon/imminent)"),
]

BY_NAME = {h.name: h for h in HEADS}

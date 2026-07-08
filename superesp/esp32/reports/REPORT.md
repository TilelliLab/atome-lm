**English** · [Français](REPORT.fr.md) · [Español](REPORT.es.md) · [简体中文](REPORT.zh-CN.md) · [Deutsch](REPORT.de.md) · [日本語](REPORT.ja.md) <!-- i18n-switcher -->

# SuperESP — application test report

_2026-06-27T17:49:41.108712+00:00_  •  source: **real ESP32 silicon**  •  **12/12 applications PASS**  •  battery completed: True

| application | status | device class | expected | free heap |
|---|---|---|---|---|
| agri | PASS | 4 | 4 (sensor_fault) | 265 KB |
| voice | PASS | 2 | 2 (stop) | 265 KB |
| motion | PASS | 0 | 0 (walking) | 265 KB |
| sound_scene | PASS | 2 | 2 (glass_break) | 265 KB |
| anomaly | PASS | 0 | 0 (normal) | 265 KB |
| air | PASS | 3 | 3 (smoke) | 265 KB |
| os_telem | PASS | 4 | 4 (power_fault) | 265 KB |
| power | PASS | 3 | 3 (electronic) | 265 KB |
| occupancy | PASS | 2 | 2 (crowded) | 265 KB |
| wearable | PASS | 3 | 3 (irregular) | 265 KB |
| water | PASS | 3 | 3 (burst) | 265 KB |
| forecast | PASS | 3 | 3 (imminent) | 265 KB |

## Bugs / errors
- none — every application reproduced its host-golden class on-device.
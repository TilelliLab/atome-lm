[English](HONEST_RESULTS.md) · [Français](HONEST_RESULTS.fr.md) · [Español](HONEST_RESULTS.es.md) · **简体中文** · [Deutsch](HONEST_RESULTS.de.md) · [日本語](HONEST_RESULTS.ja.md) <!-- i18n-switcher -->

# SuperESP — 诚实结果

> 由 `make_results_doc.py` 从 `artifacts/RESULTS.json` 生成。每个数字都来自一个留出的 TEST 切片。REAL = 真实的公开数据集；SYNTH = 物理风格的替身（已标注，非现场主张）。

## 表 1 — 逐头留出精度 + 弃权 + delta

| 头 | 数据 | 类别 | 参数 | TEST acc | 弃权 AURC（oracle/rand） | cov@≤5% 风险 | blob B | delta@0.05 |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| SuperESP-Agri | SYNTH | 5 | 20512 | 0.976 | 0.0015 (0.0003/0.0244) | 1.00 | 6633 | 8.41x/err0.0179 |
| SuperESP-Voice | REAL | 4 | 20480 | 0.625 | 0.7297 (0.3700/0.7250) | 0.00 | 6625 | N/A (tabular) |
| SuperESP-Motion | REAL | 6 | 20544 | 0.811 | 0.0644 (0.0191/0.1891) | 0.53 | 6641 | N/A (tabular) |
| SuperESP-Sound-Scene | SYNTH | 4 | 20480 | 0.975 | 0.0064 (0.0003/0.0250) | 1.00 | 6625 | N/A (tabular) |
| SuperESP-Anomaly | SYNTH | 4 | 20480 | 0.937 | 0.0290 (0.0020/0.0633) | 0.96 | 6625 | 4.19x/err0.0161 |
| SuperESP-Air | SYNTH | 4 | 20480 | 0.978 | 0.0000 (0.0000/0.0000) | 1.00 | 6625 | 6.77x/err0.01 |
| SuperESP-OS | SYNTH | 5 | 20512 | 0.987 | 0.0007 (0.0001/0.0133) | 1.00 | 6633 | 4.27x/err0.0106 |
| SuperESP-Power | SYNTH | 4 | 20480 | 0.981 | 0.0007 (0.0002/0.0194) | 1.00 | 6625 | 8.28x/err0.0142 |
| SuperESP-Occupancy | SYNTH | 3 | 20448 | 0.984 | 0.0008 (0.0001/0.0159) | 1.00 | 6617 | 8.15x/err0.0127 |
| SuperESP-Wearable | SYNTH | 4 | 20480 | 0.983 | 0.0005 (0.0001/0.0167) | 1.00 | 6625 | 8.4x/err0.0098 |
| SuperESP-Water | SYNTH | 4 | 20480 | 0.989 | 0.0001 (0.0001/0.0111) | 1.00 | 6625 | 8.53x/err0.0114 |
| SuperESP-Forecast | SYNTH | 4 | 20480 | 0.831 | 0.0554 (0.0152/0.1690) | 0.59 | 6625 | 9.19x/err0.0151 |

**12 个头的平均留出精度：0.921**（最小 0.625，最大 0.989）。

## 表 2 — Python↔C 一致性（逐位精确）

- 已测试头上的最大 |Δ logit|：**1.430511474609375e-06**（容差 1e-3）；argmax 一致：True。

## 表 3 — 认证

- 12/12 个头 blob 经 Ed25519 签名并验证；篡改（blob/元数据/签名）被拒绝（见 tests/test_attest.py）。

## 尚未测量的内容

- 硅片上的 tok/s、RAM 高水位、实时 ADC/I2S 捕获——构建机中没有物理 ESP32。固件是一个仅构建的骨架。

- SYNTH 头是物理风格的替身，不是现场部署。

## 护城河（moat）裁定

- 各个头是一个真实的步骤 / 一个应用化产品，**而非护城河**（TinyML 已拥挤）。可防御的角度 = 微型三元 + 逐位可审计 + 已认证 + delta 高效的统一 OS（先发/集成的赌注）。

[English](HONEST_RESULTS.md) · [Français](HONEST_RESULTS.fr.md) · [Español](HONEST_RESULTS.es.md) · [简体中文](HONEST_RESULTS.zh-CN.md) · [Deutsch](HONEST_RESULTS.de.md) · **日本語** <!-- i18n-switcher -->

# SuperESP — 誠実な結果

> `make_results_doc.py` により `artifacts/RESULTS.json` から生成。すべての数値は留め置きの TEST 分割からのものです。実 = 実際の公開データセット；SYNTH = 物理風のスタンドイン（明記済み、現場の主張ではない）。

## 表 1 — ヘッドごとの留め置き精度 + 棄権 + delta

| ヘッド | データ | クラス | パラメータ | TEST acc | 棄権 AURC（oracle/rand） | cov@≤5% リスク | blob B | delta@0.05 |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| SuperESP-Agri | SYNTH | 5 | 20512 | 0.976 | 0.0015 (0.0003/0.0244) | 1.00 | 6633 | 8.41x/err0.0179 |
| SuperESP-Voice | 実 | 4 | 20480 | 0.625 | 0.7297 (0.3700/0.7250) | 0.00 | 6625 | N/A (tabular) |
| SuperESP-Motion | 実 | 6 | 20544 | 0.811 | 0.0644 (0.0191/0.1891) | 0.53 | 6641 | N/A (tabular) |
| SuperESP-Sound-Scene | SYNTH | 4 | 20480 | 0.975 | 0.0064 (0.0003/0.0250) | 1.00 | 6625 | N/A (tabular) |
| SuperESP-Anomaly | SYNTH | 4 | 20480 | 0.937 | 0.0290 (0.0020/0.0633) | 0.96 | 6625 | 4.19x/err0.0161 |
| SuperESP-Air | SYNTH | 4 | 20480 | 0.978 | 0.0000 (0.0000/0.0000) | 1.00 | 6625 | 6.77x/err0.01 |
| SuperESP-OS | SYNTH | 5 | 20512 | 0.987 | 0.0007 (0.0001/0.0133) | 1.00 | 6633 | 4.27x/err0.0106 |
| SuperESP-Power | SYNTH | 4 | 20480 | 0.981 | 0.0007 (0.0002/0.0194) | 1.00 | 6625 | 8.28x/err0.0142 |
| SuperESP-Occupancy | SYNTH | 3 | 20448 | 0.984 | 0.0008 (0.0001/0.0159) | 1.00 | 6617 | 8.15x/err0.0127 |
| SuperESP-Wearable | SYNTH | 4 | 20480 | 0.983 | 0.0005 (0.0001/0.0167) | 1.00 | 6625 | 8.4x/err0.0098 |
| SuperESP-Water | SYNTH | 4 | 20480 | 0.989 | 0.0001 (0.0001/0.0111) | 1.00 | 6625 | 8.53x/err0.0114 |
| SuperESP-Forecast | SYNTH | 4 | 20480 | 0.831 | 0.0554 (0.0152/0.1690) | 0.59 | 6625 | 9.19x/err0.0151 |

**12 ヘッドにわたる平均留め置き精度：0.921**（最小 0.625、最大 0.989）。

## 表 2 — Python↔C 一致（ビット単位で厳密）

- テストしたヘッドにわたる 最大 |Δ logit|：**1.430511474609375e-06**（許容差 1e-3）；argmax の一致：True。

## 表 3 — 認証

- 12/12 のヘッド blob を Ed25519 で署名・検証；改ざん（blob/メタデータ/署名）は拒否されます（tests/test_attest.py を参照）。

## 測定していないもの

- シリコン上の tok/s、RAM 高水位、ライブ ADC/I2S 捕捉——ビルドボックスに物理的な ESP32 はありません。ファームウェアはビルド専用の骨格です。

- SYNTH ヘッドは物理風のスタンドインで、現場デプロイではありません。

## 堀（moat）の評決

- 個々のヘッドは本物のステップ / 応用製品であり、**堀ではありません**（TinyML は混雑）。防御可能な角度 = 極小三値 + ビット単位で監査可能 + 認証済み + delta 効率的な統一 OS（先行者/統合の賭け）。

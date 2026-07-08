[English](agri.md) · [Français](agri.fr.md) · [Español](agri.es.md) · [简体中文](agri.zh-CN.md) · [Deutsch](agri.de.md) · **日本語** <!-- i18n-switcher -->

# SuperESP ヘッドレポート — agri

留め置き TEST 精度：**0.953**（n=450）  •  棄権 AURC **0.0053**（oracle 0.0011、ランダム 0.0467）

## 混同行列（行 = 真、列 = 予測）

| 真 \\ 予測 | healthy | needs_irrigate | frost_risk | pest_favorable | sensor_fault |
|---|---|---|---|---|---|
| healthy | **87** | 0 | 0 | 0 | 3 |
| needs_irrigate | 0 | **90** | 0 | 0 | 0 |
| frost_risk | 0 | 0 | **90** | 0 | 0 |
| pest_favorable | 0 | 0 | 0 | **90** | 0 |
| sensor_fault | 17 | 1 | 0 | 0 | **72** |

## クラスごとの再現率
- healthy：0.967（87/90）
- needs_irrigate：1.000（90/90）
- frost_risk：1.000（90/90）
- pest_favorable：1.000（90/90）
- sensor_fault：0.800（72/90）

## リスク vs カバレッジ（低マージン入力で棄権）
| カバレッジ | リスク |
|---|---|
| 0.50 | 0.000 |
| 0.70 | 0.006 |
| 0.90 | 0.017 |
| 1.00 | 0.047 |

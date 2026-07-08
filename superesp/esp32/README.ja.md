[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · **日本語** <!-- i18n-switcher -->

# SuperESP ESP32 アプリケーションテストバッテリー

**12 個の SuperESP アプリケーションすべてを、実際の ESP32 上で 1 コマンドでテスト**し、
アプリケーションごとのレポート（合否、デバイス上のクラス vs 期待値、空きヒープ、バグ）を得ます。

> 最初にテストしたボード：**ESP32-WROOM-32**（ESP32-D0WD-V3、4 MB フラッシュ、PSRAM なし、
> /dev/ttyUSB0 @ 115200）。SuperESP の状態は約 27 KB（944K LM の 159 KB に対し）で、
> 大きな余裕を持って収まります——`superesp/cli.py targets` を参照。

## 1 コマンド（あなたのマシンで、ボード接続済み）
```bash
. ~/esp-idf/export.sh           # once per shell (install: superesp/cli.py setup)
./superesp/esp32/run_battery.sh # doctor→detect→build→flash→capture→grade→report
# env overrides: PORT=/dev/ttyUSB0 TARGET=esp32 CAPTURE_S=60
```
出力：`superesp/esp32/reports/REPORT.md` + `report.json` + 生の `serial_*.log`。

## それが行うこと
1. **gen_battery.py** が 12 個のヘッド blob + 各テストベクトル + **ホスト C のゴールデン
   期待クラス**を `battery_data.h`（+ `golden.json`）に焼き込みます。
2. **battery_main.c**（単一ソース、QEMU *と* ESP-IDF の両方でコンパイル）が各
   ヘッドを読み込み、そのベクトルを分類し、
   `HEAD <name> CLASS <got> EXPECT <want> PASS|FAIL HEAP <kb>` を出力します。
3. **parse_report.py** がシリアルログをゴールデンと照らして採点 → アプリケーション
   ごとのレポート。誠実に**実シリコン**（HEAP あり）vs **QEMU/エミュレーション**と明記。

## エミュレーションで既に検証済み（このリポジトリ、ボードなし）
まさにそのファームウェアが `qemu-system-arm`（Cortex-M3、実 ARM Thumb）で実行されました：
**12/12 アプリケーションが合格、ビット単位で厳密**（単一ヘッドは `python3 -m superesp.qemu_test <head>`）。
したがってロジックは書き込む前に証明されています——ボード実行は「エミュレーションで正しい」を
「シリコンで正しい」に変え、実際のヒープ/タイミングの数値を加えます。

## 何かが失敗したら
レポートの **Bugs / errors** セクションが捕捉します：欠落したヘッド（シリアルが
途切れる / 実行されなかった）、`LOAD_FAIL`（フラッシュ/blob の問題）、クラスの不一致、
疑わしいクラッシュ（`Guru Meditation` / `BATTERY DONE` なしの panic）。
`reports/REPORT.md` を返信に貼ってください。診断します。

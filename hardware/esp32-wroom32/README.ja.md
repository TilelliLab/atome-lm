[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · **日本語** <!-- i18n-switcher -->

# 実シリコン上の Atome — ESP32-WROOM-32

同梱の **944K** Atome チェックポイントが、**物理的な ESP32-WROOM-32**
（ESP32-D0WD-V3、4 MB フラッシュ、**PSRAM なし**）で動作し、**完全オフライン**で
首尾一貫したテキストを **約 1.0 tok/s**（240 MHz コア、80 MHz フラッシュ）で生成します。
これはリポジトリ自身の `c_engine`——ホストのユニットテストと QEMU Cortex-M3 の一致
テストを通す、まさに同じエンジン——が、いま実ハードウェアで検証されたものです。

> **誠実な範囲。** これは*実行の証明 + 再現性*の成果物であり、ベンチマークの勝利や
> 堀（moat）ではありません。MCU 上の sub-1M LM で約 1 tok/s は既知の領域です
> （cf. `llama2.c`-on-MCU、TinyML）。代替案との同一チップでの一騎打ちは実施していません
> ——それは将来の作業であり、ここでの主張ではありません。スループットはフラッシュ
> 律速です（トークンごとに約 270 KB の三値重みを SPI フラッシュから読む）。

実測出力（`evidence/serial_boot_log_esp32_wroom32.txt`）：

```
config : d=256 layers=8 head=64 seq=24  state=159 KB   (cpu 240 MHz, flash 80 MHz)
Once    ->  upon a time, there
The dog ->  was so excited.
A girl  ->  was so happy to h
average: 1.0 tok/s
```

## 約 2 分で自分で検証（ESP-IDF 不要）
GitHub Release からビルド済みの `atome_esp32_merged.bin` を入手し、次に：
```bash
pip install esptool pyserial
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash 0x0 atome_esp32_merged.bin
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200      # press the board's EN button
```
先に Release 内の `SHA256SUMS` に対してバイナリを照合してください。

## ソースからのビルド
ESP-IDF v5.3 が必要です。`atome.sh` は 検出 → ビルド → 書き込み → 監視 を包み、
（書き込みホストに IDF なしで）素の `esptool` でも書き込めます：
```bash
./atome.sh detect                 # identify the board
. ~/esp-idf/export.sh
TARGET=esp32 ./atome.sh build wroom
TARGET=esp32 ./atome.sh flash
./atome.sh monitor
```

## ビルドプロファイル（エンジンはコンパイル時にサイズ設定される → 1 バイナリ = 1 モデル）
| プロファイル | 出力 | 状態 RAM | ボード |
|---------|--------|-----------|-------|
| `full`  | 首尾一貫、フルコンテキスト（seq=128）  | ~811 KB | PSRAM（S3 …R8 / WROVER） |
| `wroom` | 首尾一貫、短いコンテキスト（seq=24）  | ~159 KB | 任意の ESP32、内部 SRAM |
| `toy`   | 退化（20 KB チェックポイント）     | ~103 KB | 任意の ESP32 |

944K の状態は品質ではなくコンテキストに応じてスケールします。古典的な ESP32 の
最大の連続 DRAM ブロックは約 168 KB（369 KB 空きだが断片化）なので、`wroom`
（seq=24 → 159 KB）が PSRAM なしのプロファイルです。PSRAM 搭載ボードは `full` を実行します。

## 注記
- `firmware/main/atome.{c,h}` は [`c_engine/upstream/atome.{c,h}`](../../c_engine/upstream/)（Apache-2.0）の同梱（vendored）コピーで、この例は単独でビルドできます。
- `firmware/main/model_full.atome` は [`checkpoints/atome_944k.bin`](../../checkpoints/) と同一バイトです（md5 `b588e45f…`）。`atome.sh build` は、選んだチェックポイントを埋め込み用に `model.atome` へコピーします。
- `build/` と `model.atome` は生成物で、git に無視されます。

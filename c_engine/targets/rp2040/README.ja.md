[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · **日本語** <!-- i18n-switcher -->

# Raspberry Pi Pico (RP2040) 上の Atome LLM

60 K パラメータの三値言語モデルを 4 ドルのマイクロコントローラで動かし、
シリアル経由で毎秒トークン数を報告する、エンドツーエンドのレシピ。

## 必要なもの

- Raspberry Pi Pico（任意の RP2040 ボード；Pico、Pico W、Pico 2、クローン）。
- USB ケーブル（オリジナル Pico は Micro-USB、Pico 2 は USB-C）。
- ツールチェーン：`arm-none-eabi-gcc`、`cmake`、`make`、`git`。
- ディスク：Pico SDK に約 500 MB + ビルドに約 50 MB。

## 一度きりのセットアップ

```bash
sudo apt install gcc-arm-none-eabi cmake make build-essential libstdc++-arm-none-eabi-newlib

git clone --depth 1 https://github.com/raspberrypi/pico-sdk
export PICO_SDK_PATH=$PWD/pico-sdk
git -C "$PICO_SDK_PATH" submodule update --init
```

## ファームウェアのビルド

プロジェクトルートから：

```bash
# 1. Train (or download) a checkpoint, then export to .atome:
python scripts/train_demo.py --data data/tinystories.txt --steps 800 \
    --output checkpoints/atome_demo.pt
python scripts/export_to_atome.py --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome

# 2. Bake the binary into a C array:
cd c_engine/targets/rp2040
xxd -i -n model_atome ../../../checkpoints/atome_demo.atome > model_data.h

# 3. Build:
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j
```

これで `build/atome_pico.uf2`（約 200 KB）ができているはずです。

## ボードの書き込み

1. Pico を USB に挿しながら、その上の **BOOTSEL** ボタンを押し続けます。
2. 離すと、ボードが **RPI-RP2** という名前の USB ドライブとしてマウントされます。
3. `atome_pico.uf2` をドライブにドラッグ&ドロップします。コピーが完了すると Pico は
   自動的に再起動します。

## 出力を読む

**115 200 8N1** でシリアル端末を開きます（`minicom -D /dev/ttyACM0 -b 115200`、
または任意のホストのシリアルアプリ）。次が見えるはずです：

```
ATOME-PICO-START prompt_len=4 new_tokens=16 max_seq=32
TOK 0 117 us=42120
TOK 1  98 us=43755
TOK 2 215 us=43818
...
ATOME-PICO-END total_us=698540 tokens=16
```

各 `TOK N B us=...` 行は、生成された 1 バイトと、RP2040 のハードウェアタイマーで
測定されたステップごとのレイテンシ（マイクロ秒、ホストのクロックは関与しない）です。
エンジン既定値（60.8 K パラメータ、4 層、`max_seq=32`）で、標準の 125 MHz RP2040 では、
Python 側の参照生成ループで概ね **15〜25 tokens/sec**、ストリーミング SSM の C パスに
切り替えれば概ね **40〜60 tokens/sec** を期待できます（プロジェクト README の Bug A を
参照——その修正はユーザーの承認が前提）。

## 電力の測定

Pico の `VBUS` ラインに 1 Ω のシャント抵抗を配線し、USB 絶縁された DMM か
Joulescope でサンプリングします。トークンあたりのジュールは、2 つの連続する `TOK`
行の間の時間にわたる電力の積分です。典型的な RP2040 のアクティブ消費は
約 30 mA @ 3.3 V → 100 mW——25 tok/s では **トークンあたり 4 mJ** です。

## トラブルシューティング

- **シリアルデバイスがない。** Pico SDK は USB CDC と UART の両方を露出します。
  `/dev/ttyACM0` が見えない場合は `dmesg | tail` で USB 列挙行を確認してください。
  それがあるのにデバイスが見えない場合、あなたのユーザーが `dialout` / `tty`
  グループにいない可能性があります。
- **`atome_load` が失敗する。** 最も一般的な原因は、学習済みチェックポイントと
  Pico 側の定義の構成不一致です。あなたのチェックポイント構成に一致する
  `cmake -DATOME_D_MODEL=... -DATOME_N_LAYERS=...` で再ビルドしてください
  （エクスポートスクリプトの出力を参照）。
- **フラッシュ不足。** 既定構成は 200 KB を大きく下回ります。`d_model` や
  `n_layers` を上げた場合、`.atome` blob が 2 MB のフラッシュを超えることがあります。
  モデルサイズを下げるか、blob を外部 SD カードに移してください
  （このファームウェアではまだ未対応）。

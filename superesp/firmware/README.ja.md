[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · **日本語** <!-- i18n-switcher -->

# SuperESP ファームウェア骨格（ESP32 / ESP-IDF）

> **状態：ビルド専用の骨格——書き込みなし、シリコン上で測定なし。**
> このマシンには物理的な ESP32 も ESP-IDF ツールチェーンもありません。下記の
> ファームウェアは実際の構造です（同梱（vendored）の `atome.c`/`atome.h` エンジンと、
> 学習済みの ATOMECL01 ヘッド blob を再利用します）が、ボード上の tok/s、RAM 高水位、
> ライブ ADC/I2S 捕捉は**ここでは測定されません**。ホスト側の C ディスパッチャ
> `c_engine/superesp/superesp_os.c` は*コンパイルされテストされています*（superesp テストを参照）。

## それが行うこと（「OS」のアイデア）
起動時、ファームウェアは：
1. ESP32 自身のテレメトリ——`esp_get_free_heap_size()`、内部温度センサー、
   Wi-Fi RSSI、ADC チャネル、hall、touch——を **OS 融合フレーム**へ読み込みます。
2. そのフレームを（`os_telem.tok.json` から焼き込まれた特徴ごとの `vmin/vmax` を用いて）
   バイトに量子化し、**OS ヘッド**で `atome_classify` を実行して
   デバイス状態（normal / low_memory / overheating / wifi_degraded / power_fault）を得ます。
3. 負荷切り離し方針を適用し（例：過熱時に音声ヘッドを無効化）、その後、
   アクティブなセンサー（agri は ADC、voice は I2S マイク）を読み、そのフレームを
   その ヘッドへ振り分けます——不確実なら棄権します。

こうして Atome はテキスト生成器ではなく、デバイスのスーパーバイザーとして動作します。
全 7 ヘッドは 1 つのエンジンビルド（同じ共有構成）を共有し、各ヘッドは異なる埋め込み blob です。

## ビルドするには（ESP-IDF + ボードのあるマシンで）
```
idf.py set-target esp32
idf.py build            # compile-time config in main/CMakeLists.txt
idf.py -p /dev/ttyUSB0 flash monitor
```
コンパイル時定義（d_model=32、n_layers=2、...）は、blob をエクスポートした際の
SuperESP 共有構成（superesp/framework/config.py）と一致していなければなりません。

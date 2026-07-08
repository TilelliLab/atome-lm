[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · **日本語** <!-- i18n-switcher -->

# SuperESP — ESP32 エッジ向けの応用 Atome-LM

SuperESP は、Atome の極小三値（1.58 ビット）モデルを、テキスト生成の*代わりに*
マイクロコントローラ上で動作する**応用ストリーミング分類器**のスイートに変えます。
加えて、ESP32 のすべてのセンサーを読み、正しいヘッドへ振り分ける、デバイス上の
**「OS」ランタイム**を備えます。

これは 2026-06-13 の Atome 堀（moat）レビューの PIVOT #1 を実現します：`atome_classify`
ヘッドは C エンジンに存在していましたが、**一度も学習されていませんでした**。SuperESP は
それを——7 つの実エッジタスクについて——学習し、delta 推論（エネルギー）、棄権
（不確実なら拒否）、暗号的な認証（監査可能性）を配線します。

## 11 のヘッド（1 つの共有エンジンビルド；各ヘッド = 異なる ATOMECL01 blob）
| ヘッド | タスク | データ |
|---|---|---|
| SuperESP-Agri | 土壌/気候 → 灌漑/霜/害虫/健全/故障 | SYNTH（農学的） |
| SuperESP-Voice | I2S マイク → 農場の音声コマンド（on/off/stop/go） | 実（Speech Commands） |
| SuperESP-Motion | IMU → 活動/ジェスチャ/転倒 | 実（UCI HAR） |
| SuperESP-Sound-Scene | 環境音 → 音響イベント | SYNTH（合成音声） |
| SuperESP-Anomaly | 振動 → 機械の健全性 | SYNTH（物理） |
| SuperESP-Air | ガス+気候 → 空気質/漏れ | SYNTH（物理） |
| SuperESP-OS | 融合された ESP32 テレメトリ → デバイス状態 + 振り分け | SYNTH（チップテレメトリ） |
| SuperESP-Power | CT クランプのエネルギー/NILM → 負荷種別 | SYNTH（物理） |
| SuperESP-Occupancy | PIR+CO2+音 → 部屋の在室 | SYNTH（物理） |
| SuperESP-Wearable | PPG+IMU → 心拍/活動状態（医療用ではない） | SYNTH（物理） |
| SuperESP-Water | 流量+圧力+水分 → 漏れ/浸水 | SYNTH（物理） |

## 速度
- **三値カーネル：** 分岐なしの 4-trit/バイト matvec → **分類 306 µs → 87 µs（3.5×）**、ホスト（-O3）で約 11,400/s。
  Atome エンジン全体（classify + generate + ESP32）に恩恵をもたらします。ビット単位の
  厳密さは保たれます（一致 最大 |Δ| 8.3e-7）；既存の 146 テストはすべて通ります。
- **変化ゲート付きストリーミング**（`framework/streaming.py`）：相関のある常時オンのストリームでは、
  入力が発火閾値を越えてドリフトしたときだけモデルを再実行し、さもなければキャッシュした
  決定を再利用します（各フレームを実行するのとビット単位で同一）。スキップ率が利得です（静止ストリームで ≈98 %）。
- **Delta 推論**（`framework/delta.py`）：相関ストリームで matvec 操作が 4〜11× 少ない。
- ESP32 シリコン上の tok/s/RAM は**未測定**（ボードなし）；ホストの高速化は引き継がれると期待。

留め置き精度、棄権 AURC、delta 推論の高速化、ヘッドごとの 実/SYNTH ラベルは、
`HONEST_RESULTS.md` / `artifacts/RESULTS.json` を参照。

## 仕組み
- **トークナイザ**（`framework/tokenize.py`）：各センサー/特徴フレームはバイト列（≤32）へ
  線形に量子化されます——そのため既存の 256 バイト語彙の Atome エンジンが変更なしで
  動作します。量子化定数は TRAIN のみでフィットされます（リークなし）。
- **モデル**（`framework/model.py`）：既存の `AtomeLM` ベース + 最後のトークンの
  final-norm 隠れ状態上の三値分類ヘッド——まさに C の `atome_classify` が計算するものです。
  **Python↔C のビット単位で厳密な一致**（最大 |Δ| ~7e-7）。
- **棄権**（`framework/abstain.py`）：top1-top2 の softmax マージンが低いときに拒否します；
  リスク-カバレッジ曲線 + oracle/ランダム に対する AURC として報告。
- **Delta 推論**（`framework/delta.py`）：相関センサーストリーム向けの積分発火 delta
  matvec——delta_inference 実験で実測されたエネルギー代理指標を、ヘッドごとに適用。
- **認証**（`attest/sign.py`）：sha256(blob) + メタデータを束ねる Ed25519 署名の
  レシート。デプロイ担当者が*この*正確なヘッドが動いたと証明できます。改ざん検知可能（tamper-evident）。
- **ランタイム**（`runtime/dispatcher.py`）：フレームをモダリティで自身のヘッドへ振り分け、
  融合テレメトリで OS ヘッドを走らせ、故障状態で負荷を切り離します。C ミラー：
  `c_engine/superesp/superesp_os.c`。ファームウェア骨格：`superesp/firmware/`。

## インストール
```
pip install -e .              # core (torch + numpy); run the CLI as: python3 -m superesp.cli <cmd>
pip install -e ".[superesp]"  # + cryptography/scipy/pyserial/esptool (attestation, audio, flashing)
```

## 任意の ESP32 を書き込む（ESP-IDF 不要——esp32/s2/s3/c3/c6/h2 向けにビルド済み）
```
bash superesp/esp32/install.sh    # auto-detects the chip, flashes the matching
                                  # prebuilt firmware, runs all heads, writes a report
```

## 数分で自分の分類器を作る（ML の技能不要——記録→学習→書き込みのループ）
```
# 1. flash the data-logger, then record YOUR sensor in each state:
python3 -m superesp.cli log --label dry --out field.csv   # leave probe in dry soil
python3 -m superesp.cli log --label wet --out field.csv   # ...then wet soil
# 2. train + see how good it is + deploy:
python3 -m superesp.cli train --csv field.csv --name myfarm
python3 -m superesp.cli report myfarm                     # confusion matrix + abstention (md + html)
python3 -m superesp.cli flashplan myfarm
# (or start from a blank template:)  python3 -m superesp.cli new myfarm --features 30
```
**9 つの SYNTH ヘッドは単なる既定値で——完全に差し替え可能です。** 組み込みの名前の下で
自分のデータで学習すれば、実世界のモデルに置き換えられます：
`python3 -m superesp.cli train --csv my_field.csv --name agri` は合成 `agri` ヘッドの blob を上書きします。
何もハードコードされていません；各ヘッドは「データで学習 → blob をエクスポート」です。

## 再現 / 自分のデータを持ち込む
```
python3 -m superesp.cli list                      # the 11 built-in heads
python3 -m superesp.cli train agri                # train+eval+export one built-in head
# YOUR sensor: rows = up to 32 features + a label column
python3 -m superesp.cli train --csv my.csv --label-col state --name mysensor
python3 -m superesp.cli flashplan mysensor        # how to bake the blob into firmware
# or everything at once:
python3 -m superesp.train_all && python3 -m superesp.attest_all
python3 -m pytest superesp/tests                  # framework, parity(gcc), attest, dispatch, streaming, csv, novelty
```
自分の ESP32 センサーウィンドウの CSV を持つ人なら誰でも、ビット単位で厳密で認証可能な
デバイス上の分類器を得られます——ML のセットアップなしで。これは商用 TinyML
パイプラインの、オープンで監査可能な対応物です。

## 誠実な範囲 / 堀（moat）
個々のヘッドは本物の応用エッジ AI（ステップ / 製品）であり、**堀ではありません**——
TinyML の KWS/ジェスチャ/異常は混雑しています（TFLite-Micro、Edge Impulse）。唯一
防御可能な角度は、**超極小の三値 + ビット単位で監査可能 + 暗号的に認証済み +
delta 効率的**という組み合わせを、統一されたデバイス上 OS として提供することです。
それは先行者/統合の賭けであり、砂場の堀ではありません。SYNTH データで学習した
ヘッドは物理風のスタンドインで、そう明記されています——現場デプロイの主張ではありません。
シリコン上のスループット/RAM は**未測定**（ボードなし）。
```
```

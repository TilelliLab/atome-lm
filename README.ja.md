[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · **日本語** <!-- i18n-switcher -->

# Atome LM

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20518644.svg)](https://doi.org/10.5281/zenodo.20518644)
[![tests](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml/badge.svg)](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Model-FFB020)](https://huggingface.co/TilelliLab/atome-lm)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

> ルーティング付き三値の極小言語モデルのリファレンス実装。ビット単位で厳密な
> Python ↔ C99 推論エンジンを備え、マイクロコントローラ級の RAM 予算に合わせて
> サイズ設定されています。

デフォルト 60K パラメータの言語モデルで、3 つの既知のアイデアを 1 つのオープンな
キットに統合しています。三値の重み（[BitNet b1.58](https://arxiv.org/abs/2402.17764) に倣う）、
トークンごとにルーティングされるハイブリッドな SSM + スパースアテンション + ローカル畳み込みブロック
（[Hymba](https://arxiv.org/abs/2411.13676) と
[MossNet](https://arxiv.org/abs/2510.26182) に倣う）、
そして超小規模でのバイトトークナイザ
（[Guertler 2024](https://arxiv.org/abs/2405.14159) に倣う）です。
**貢献はアーキテクチャではなく統合にあります**。すなわち、学習 →
三値へのエクスポート → 3 進パッキング → C99 推論という完全な経路を、
テストによって強制される Python ↔ C のビット単位で厳密な一致とともに提供します。

**クイックリンク：**
- 📄 アーキテクチャの解説：[`PAPER.md`](PAPER.ja.md)
- 🔬 誠実な結果（944 K での逆転を含む）：[`HONEST_RESULTS.md`](HONEST_RESULTS.ja.md)
- 🌐 ブラウザ内ライブデモ（インストール不要）：[atomelm.com/demo.html](https://atomelm.com/demo.html)
- 🏠 プロジェクトホーム：[atomelm.com](https://atomelm.com)

**キットを入手：** 学習コード、C エンジン、ベンチマーク、論文、学習済みの
重み——すべてこのリポジトリ内にあり、
[Apache 2.0 ライセンス](LICENSE) の下で公開されています。CPU 上で約 30 分、
`scripts/train_demo.py` で自分のチェックポイントを学習することも、同梱の 944 K
チェックポイントをすぐに実行することもできます。

**MCU の状態：** QEMU ARM（Cortex-M3、MPS2-AN385）の一致は FP32 の
epsilon まで通り、再現可能な**実シリコンのデモ**が物理的な **ESP32-WROOM-32** 上で
944 K チェックポイントを実行します——首尾一貫したテキスト、完全オフライン、約 1 tok/s——
[`hardware/esp32-wroom32/`](hardware/esp32-wroom32/) を参照（ビルド済みバイナリ + シリアルログ
+ ワンコマンド書き込み）。このデモはあくまで実行の証明です。**製品化された立ち上げ**——
Atome Secure Boot Pack（署名済み `.atome` blob、dev/prod フラグ、プラットフォーム別の
secure-boot、認証（アテステーション））やプラットフォーム別のハードニング——は、
統合サービスとして [atomelm.com](https://atomelm.com) で販売しています。

**重みは同梱されています**（`checkpoints/` 内）：

- `atome_944k.bin`（271 KB）——パック済みの C エンジン blob（`ATOME01` 形式）。
  推論エンジンが直接読み込めます。
- `atome_1m_v1.pt`（3.7 MB）——それを生成した PyTorch のソースチェックポイント。
  ファインチューニングや、異なる `#define` での再エクスポートに使います。
- `vanilla_1m_v1.pt`（3.7 MB）——[`HONEST_RESULTS.md`](HONEST_RESULTS.ja.md) の
  944K A/B 逆転に用いた FP32 vanilla GPT ベースライン。
  比較をエンドツーエンドで再現できるよう同梱しています。

944K チェックポイントは研究用デモの成果物であり、製品ではありません。狭く、時に
一貫性を欠き、単一のコーパスで学習されています。これはアーキテクチャを*実行可能*に
するためにあり、品質の基準を設定するためではありません。同梱の学習コードでの再現は
CPU/GPU で約 1〜2 ドル。このキットには再現の障壁となるものは何もありません。

---

## 再現可能な結果、狭いレジーム

TinyStories 上、3000 ステップ、単一シード：固定パラメータ数では、Atome の
三値ルーティングブロックは vanilla GPT-FP32 ベースラインの 8.12 に対し **6.31 ppl**
（−22 %）に達します。固定フラッシュ予算では **6.31 対 13.10**（−52 %）。ディスク
フットプリントはパラメータ一致時に 16 倍小さくなります（15.1 KB 対 237.5 KB）。

**この結果は 944 K パラメータで逆転し**、vanilla FP32 ベースラインが約 11 % 勝ちます。
Atome の賭けは意図的に sub-1M、MCU 級のレジームにあります。それを超えると三値の
容量上限が差を埋め、追い越します。完全な再現は
[`FRONTIER.md`](FRONTIER.ja.md)、逆転を含む完全で誠実な読み解きは
[`HONEST_RESULTS.md`](HONEST_RESULTS.ja.md) にあります。

## なぜ

データセンターの LLM はデータセンターの RAM を前提とします。遠隔センサーの壁に貼り付いた 2 ドルのマイクロコントローラ、補聴器、電池駆動のおもちゃ、サーモスタットには、それがありません。Atome LM は、その制約のモデル設計側の答えです：

- **三値の重み**（テンソルごとに `{-α, 0, +α}`、BitNet b1.58 スタイル）。推論時の行列積に浮動小数点乗算はありません。
- **3 経路ブロック**（ローカルの depthwise 畳み込み、対角 SSM、top-k スパースアテンション）を、トークンごとのソフトルーターで混合します。Atome C99 エンジンの構造体に正確に一致するよう設計されており、学習済みチェックポイントはフラッシュにエクスポートされ、Python と C の間で**ビット単位で厳密な一致**をもって動作します。
- **バイトトークナイザ。** 出荷すべき BPE テーブルはありません。
- **校正信号としてのルーターのエントロピー。** トークンごとのルーター分布のエントロピーは、各位置で無償で観測できます。Atome-LLM のエンジン既定である 60 K パラメータ規模、単一の狭いコーパスでは、この信号は露出していますが、この規模での不確実性推定器としての校正はここでは測定していません。私たちは*予備的に*観測しました（**本リリースには含まれない**より大きな 3 M パラメータのモデルで）——エントロピーがドメイン外の入力を追跡し、トークンごとの損失と相関することを。ここでは、まだ公開していない観測として報告し、測定は将来のリリースで続きます。

## これは何であり、何でないか

- **である：** セント級のハードウェアで動作する三値 LM の Python 学習側とアーキテクチャ。
- **でない：** 汎用チャットボット。エンジン既定の設定（`d_model=64`、`n_layers=4`）では、モデルはおよそ 60 K パラメータで、約 20 KB のフラッシュにエクスポートされます。狭く学習させれば——単一のドメイン（組み込みシステムの Q&A、コマンドラインのヘルプ、1 つの FAQ）——その範囲内では流暢に話します。このサイズで広く展開すると一貫性を欠く出力になります。それはアーキテクチャではなく容量の反映です。より余裕が欲しければ、`d_model` と `n_layers` を上げ（例：`d_model=128, n_layers=6` ≈ 600 K パラメータ、パック後約 150 KB）、対応する `#define` で再エクスポートしてください。

## インストール

```bash
./install.sh          # CPU-only venv + dependencies + environment check
```

または手動で：`pip install -e .`（Python ≥ 3.10、PyTorch ≥ 2.0）。初めてですか？
[`QUICKSTART.md`](QUICKSTART.ja.md) は、クローンからマイクロコントローラ対応モデルまでの
60 秒の道のりです。

## クイックスタート

```python
import torch
from atome_llm.core.atome_lm import AtomeLM

# Defaults match the Atome C99 engine's compile-time #defines:
#   d_model=64, n_layers=4, d_head=16, top_k=4, kernel=5, vocab=256.
model = AtomeLM()
print(f"params: {model.parameter_count():,}")

ids = torch.randint(0, 256, (1, 32))
logits = model(ids)                     # (1, 32, 256)
loss = model.loss(ids[:, :-1], ids[:, 1:])

# Per-layer per-token uncertainty signal — no extra training:
ent_per_layer = model.router_entropies(ids)   # list of (B, L) tensors
```

## 小さなデモを学習する

```bash
python scripts/train_demo.py --data path/to/text.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

組み込みの `build_corpus.py` は、スモーク学習用にいくつかの寛容なライセンスの
ソース（`tinystories`、`esp-idf`、`mcu-wikipedia`）を取得します：

```bash
python scripts/build_corpus.py --source tinystories --max-bytes 500000 \
    --output data/tinystories.txt
```

## チェックポイントを試す

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
# or, with no checkpoint, sanity-check the plumbing:
python scripts/demo.py --random --temperature 0.8 --top-p 0.9
```

REPL はプロンプトの上に、続きの生成と層ごとのルーターエントロピーのバーを表示します——無償で露出しているメタ認知信号です。

## サンプリング

`AtomeLM.generate(...)` は既定で貪欲な argmax（C エンジンの
`atome_predict_next` に一致）を使います。オプションの `temperature`、`top_p`、`top_k`、
`generator=` 引数で、シードによる再現性を伴う nucleus / top-k サンプリングを有効にできます。

## ベンチマーク

```bash
python scripts/benchmark.py            # tiny / default / large
```

3 つの代表的な設定での CPU の forward + generate のレイテンシ。アーキテクチャ変更後の回帰チェックとして有用です。MCU の数値ではありません。

## マイクロコントローラへのエクスポート

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header
```

これは C から `#include` でき、[Atome C99 エンジン](c_engine/) の `atome_load(...)` で読み込めるフラットな `.atome` バイナリを生成します。既定設定ではバイナリは 100 KB を大きく下回り——ESP32-S3、STM32F4、RP2040、nRF52840、ESP32-C3 に余裕をもって収まります。

## アーキテクチャ

```
x → LayerNorm → ┬─→ Local  (depthwise causal conv k=5)        ─→┐
                ├─→ State  (diagonal SSM, O(L))                 ─→ Σ → +x
                └─→ Sparse (top-k attention, O(L·k))            ─→┘
                        ↑              ↑
                        │              router weights r ∈ Δ per token
                        └──────────────┘
```

3 つの経路。3 つの異なる帰納バイアス。各位置にどの経路が最も適切かを学習する、トークンごとの共有ルーター 1 つ。ルーターのトークンごとのエントロピーは、各層で無償の位置ごとの不確実性信号として露出します。

アーキテクチャの完全な物語は [`PAPER.md`](PAPER.ja.md) にあります。

## テスト

```bash
pytest -q
```

## ライセンス

Apache License 2.0——[`LICENSE`](LICENSE) と [`NOTICE`](NOTICE) を参照。

キットは完全にオープンです。座席ごと・デバイスごとの料金なしに、使用、改変、再配布し、商用製品に組み込んで出荷できます。Apache 2.0 の特許許諾は、ここで公開された 3 経路の三値ルーティングアーキテクチャを対象とします。

`checkpoints/` 内の公開チェックポイント（atome_944k.bin、atome_1m_v1.pt、vanilla_1m_v1.pt）も同様に Apache-2.0 です。これらはリファレンス / 研究用の成果物であり、製品ではありません。商用統合——シリコンの立ち上げ、Atome Secure Boot Pack（署名済み `.atome` blob、dev/prod フラグ、プラットフォーム別の secure-boot、認証）、プラットフォーム別のハードニング、より大きな内部 V2 モデルのカスタムドメイン向けファインチューニング——は [atomelm.com](https://atomelm.com) で提供しています。

## 引用

```bibtex
@software{atome_llm_2026,
  title  = {Atome LM: a tiny ternary language model for microcontroller deployment},
  author = {Atome LM contributors},
  year   = {2026},
  note   = {Apache 2.0, https://atomelm.com},
}
```

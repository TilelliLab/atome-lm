[English](QUICKSTART.md) · [Français](QUICKSTART.fr.md) · [Español](QUICKSTART.es.md) · [简体中文](QUICKSTART.zh-CN.md) · [Deutsch](QUICKSTART.de.md) · **日本語** <!-- i18n-switcher -->

# Atome LM — クイックスタート

クローンから、学習済みでマイクロコントローラ対応のモデルまでの 60 秒の道のり。
完全な物語は [README.md](README.ja.md) と [REPRODUCE.md](REPRODUCE.ja.md) を参照。

## 1. インストール（CPU のみ、GPU なし）

```bash
./install.sh
. .venv/bin/activate
```

`install.sh` はローカルの `.venv` を作成し、CPU 専用の PyTorch と Atome
LM をインストールし、`check_env.py` を実行します。環境を再検証するには、いつでも
`python check_env.py` を再実行してください。

## 2. 小さなデモモデルを学習する

寛容なライセンスの TinyStories コーパスの約 256 KB のサンプルが
`data/sample.txt` に同梱されているため、これはオフラインで実行できます：

```bash
python scripts/train_demo.py --data data/sample.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

より大きなコーパスには、同梱のビルダーで 1 つ取得してください：

```bash
python scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt
```

## 3. 話しかける

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
```

REPL は続きの生成と、層ごとのルーターエントロピーのバーを表示します——無償のトークンごとの不確実性信号です。

## 4. マイクロコントローラへエクスポート

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome --header
```

既定設定では、`.atome` バイナリは 100 KB を大きく下回ります。生成された
`.h` を C プロジェクトに入れ、`c_engine/` のエンジンで読み込んでください。

## 5. テストを実行する

```bash
pytest -q
```

QEMU Cortex-M3 の一致テストは `qemu-system-arm`、`arm-none-eabi-gcc`、
`xxd` が `PATH` にあることを必要とします。ツールチェーンがない場合、それらは
**スキップ**されます（失敗ではなく skipped）。

---

**学習済みの重みは同梱されています**（`checkpoints/` 内）——`atome_944k.bin`
（パック済み C エンジン blob）、`atome_1m_v1.pt`（PyTorch ソース）、
`vanilla_1m_v1.pt`（[HONEST_RESULTS.md](HONEST_RESULTS.ja.md) の 944 K 逆転 A/B 用の
FP32 ベースライン）。先に学習せずにモデルを実行したい場合：

```bash
python scripts/demo.py --checkpoint checkpoints/atome_1m_v1.pt
```

自分のものをゼロから学習したい場合は、上記の
`scripts/train_demo.py` の流れに従ってください——CPU 上で約 30 分で 60 K
パラメータのモデルを生成します。

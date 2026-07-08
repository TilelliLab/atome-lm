[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · **日本語** <!-- i18n-switcher -->

# Atome LLM — 同梱（vendored）C エンジン

このディレクトリには、Atome LLM のチェックポイントをマイクロコントローラおよびホスト上で実行する C99 推論エンジンが含まれます。プロジェクトの Python 側（`atome_llm/`）が学習とエクスポートを行い、ここの C 側がエクスポートされた `.atome` バイナリを読み込んで、デバイス上で forward パスを実行します。

## レイアウト

```
c_engine/
├── README.md                  this file
├── upstream/
│   ├── atome.h                public API + compile-time #defines
│   └── atome.c                implementation (~570 lines, zero-heap, integer-arithmetic forward)
└── targets/
    └── cortex-m3/             ARM Cortex-M3 firmware that runs in QEMU MPS2-AN385
        ├── firmware.c
        ├── startup.s
        ├── linker.ld
        └── Makefile
```

## これがどこから来たか

`upstream/` のファイルは、2026-05-03 時点の内部 C エンジンソースの同梱（vendored）コピーです。同梱（サブモジュールやシンボリックリンクではなく）は意図的なものです：atome-llm が配布の単位であるべきだからです。upstream の変更を取り込むには、ファイルを再コピーし、一致テストスイートを再実行してください（`pytest tests/test_parity_with_c.py tests/test_qemu_parity.py`）。

逐語的な upstream からの小さな差分が 1 つ：`atome.h` の 1 つのコメントが「Atome block」に改名されました（以前の名称を指していた）。機能的な変更はありません——コメントはコンパイルされません。

## ホスト向けのコンパイル（x86-64）

最も単純な経路——`tests/test_parity_with_c.py` が使用：

```bash
gcc -O2 -std=c99 -DATOME_D_MODEL=16 -DATOME_N_LAYERS=2 ... \
    -I c_engine/upstream parity_main.c c_engine/upstream/atome.c -lm
```

## ARM Cortex-M 向けのコンパイル

2 つの層：

1. **コンパイルのみの健全性チェック**、複数の Cortex-M バリアントにわたる——`python scripts/cross_compile.py` がサイズ表（アーキテクチャごとの `text/data/bss`）を生成します。可搬性の退行を捕捉し、実際のターゲット上のバイナリサイズ数値を与えます。
2. **完全なファームウェア**、QEMU MPS2-AN385 向け——`make -C c_engine/targets/cortex-m3` が、セミホスティング付きで `qemu-system-arm` の下で動く `.elf` を生成します。エンドツーエンドの Python ↔ Cortex-M3 一致テストは `tests/test_qemu_parity.py` にあります。

## アーキテクチャに関する注記

C エンジンは次を前提とします：
- テンソルごとの三値スケール（重み行列ごとに 1 つの FP32）
- 埋め込みレイアウト `(vocab, d_model)`——なぜこれが重要かは `atome_llm/core/ternary_embedding.py` を参照
- 行ごとのスケールなし、マルチバンクの重みなし、位置埋め込みなし
- `atome_block_t` は `local_conv`、`ssm`、`attn`、`router` のみに固定バッファを持つ——広い畳み込みなし、密な FFN なし、検索経路なし

これらの制約は支えとなるものです。新しい経路を追加するには、`atome.h`、C カーネル、`.atome` バイナリ形式、**および** Python の `MCUBlock` を一緒に更新する必要があります。

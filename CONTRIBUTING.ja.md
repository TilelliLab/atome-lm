[English](CONTRIBUTING.md) · [Français](CONTRIBUTING.fr.md) · [Español](CONTRIBUTING.es.md) · [简体中文](CONTRIBUTING.zh-CN.md) · [Deutsch](CONTRIBUTING.de.md) · **日本語** <!-- i18n-switcher -->

# Atome LM への貢献

貢献をご検討いただきありがとうございます。これは小さく焦点を絞ったプロジェクトです——極小の三値言語モデル + それとビット単位で厳密に対話する C99 推論エンジン。まず `PROJECT_CONTENT.md` を読んでください。壊してはならないものが書かれています。

## クイックスタート

```bash
git clone https://github.com/TilelliLab/atome-lm
cd atome-lm
./install.sh
. .venv/bin/activate
pytest -q        # expect: 146 passed (or 145 + 1 skipped without qemu-system-arm)
```

## バグの報告

GitHub で issue を開き、次を添えてください：

- 実行したこと（正確なコマンド）
- 期待したこと
- 起きたこと（言い換えではなく、完全なエラー）
- あなたのプラットフォーム：OS、Python バージョン、`python -c "import torch; print(torch.__version__)"`

一致の失敗（Python の forward ≠ C の forward）に遭遇した場合は、失敗するシードと、学習した任意のチェックポイントを添付してください——これらは最優先のバグです。

## プルリクエストの提出

1. リポジトリを fork し、`main` からブランチを作成します。
2. 変更を行います。
3. 完全なテストスイートを実行します——すべての PR は `pytest -q` を緑に保たねばなりません。
4. 変更が `atome_llm/core/`、`c_engine/upstream/`、またはエクスポート形式に触れる場合は、これらのテストが依然として通ることを**特に確認**してください：
   - `tests/test_parity_with_c.py` — 単一 forward の Python ↔ C 一致
   - `tests/test_parity_multitoken.py` — マルチトークンの Python ↔ C 一致
   - `tests/test_export_format.py` — バイナリ形式 + ヘッダ生成
5. PR を開きます。CI が Python 3.10 / 3.11 / 3.12 でスイートを再実行します。

## 受け入れ可能な変更の範囲

歓迎：

- バグ修正
- 新しいテストカバレッジ（特に C パーサへのファズケース、`atome_predict_next` / `atome_generate` への境界入力）
- ビット単位で厳密な一致を保つ性能改善
- ドキュメントの修正と明確化
- `c_engine/targets/` 下の新しい MCU ターゲットボード（*upstream エンジンを変更しない限り*）
- 誠実な A/B 比較のための `atome_llm/baselines/` 下の新しいベースライン

範囲外、これらの PR は開かないでください：

- `c_engine/upstream/` へのヒープ割り当て、動的メモリ、libc 依存の追加
- 決定的なコードパスへの「起こるはずがない」フォールバックの追加
- 新しいトークナイザ（BPE / sentencepiece）の同梱——バイトトークナイザは MCU のフラッシュ予算にとって支えとなる設計上の選択です
- ベンチマークを改善するとしても、Python ↔ C の一致を破る変更
- 完全な一致 + 境界チェックのカバレッジなしに `c_engine/experiments/` から `c_engine/upstream/` へコードを昇格させる新機能

## コーディング規約

- Python：シンプルに保ち、ヘルパー層なし、スタイルのためのデコレータなし。既存の語り口に合わせる——小さな関数、早すぎる抽象化なし、*なぜ*が自明でないときだけコメント。
- C：C99 のみ、GNU 拡張なし、`<string.h>` / `<math.h>` / `<stdint.h>` を超える libc なし。コンパイル時 `ATOME_*` マクロでサイズ設定された静的バッファ。すべての公開 API 入力の境界チェック。

## セキュリティ

セキュリティ問題（悪意あるチェックポイントや `.atome` blob が、エンジンを実行するホストを侵害できるもの）を見つけた場合は、公開の issue を提出する代わりに **hello@atomelm.com** へメールしてください。開示を調整します。

## ライセンス

貢献を提出することで、それが Apache License 2.0（プロジェクトライセンス——`LICENSE` を参照）の下で公開されることに同意したものとします。

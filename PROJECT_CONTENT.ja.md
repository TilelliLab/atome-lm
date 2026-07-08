[English](PROJECT_CONTENT.md) · [Français](PROJECT_CONTENT.fr.md) · [Español](PROJECT_CONTENT.es.md) · [简体中文](PROJECT_CONTENT.zh-CN.md) · [Deutsch](PROJECT_CONTENT.de.md) · **日本語** <!-- i18n-switcher -->

# PROJECT_CONTENT.md — プロジェクトの手引き

まずこれを読んでください。コードベースにやって来る誰か（人間でもエージェントでも）のための約 5 分の手引きです。このキットが重視する、支え（load-bearing）となる不変条件を壊さずに済みます。

---

## 要約（TL;DR）

**Atome LM** は、約 60K パラメータの三値言語モデル + それをベアメタルのマイクロコントローラ（RP2040、ESP32-C3、Cortex-M0）で実行する C99 推論エンジンです。Python の学習スタックと C エンジンは、**ビット単位で完全に同一**の forward パスを生成するよう設計されています——その一致こそがプロジェクトの要点です。

- ライセンス：Apache 2.0
- テスト：`pytest -q` → 期待値は **146 passed, 0 skipped**（`qemu-system-arm` がなければ 1 skip）
- 3 つの学習済みチェックポイントが `checkpoints/` で出荷されます：`atome_944k.bin`（271 KB のパック済み C エンジン blob——`ATOME01` 形式の 944K パラメータのデモモデル）、`atome_1m_v1.pt`（それを生成した PyTorch ソース）、`vanilla_1m_v1.pt`（HONEST_RESULTS の A/B に用いた FP32 vanilla GPT ベースライン）。`*.pt`/`*.atome*`/`*.bin` に一致する*その他*のものはすべて git に無視されます。代わりにゼロから学習するには `scripts/train_demo.py` を使ってください（約 30 分 CPU）。

## なぜ存在するか

ほとんどの「極小 LM」は、圧縮された大型 LM です。Atome は最初から MCU の制約によって形作られています：RAM が拘束的コスト、三値の重みが浮動小数点乗算を消し、3 経路（ローカル畳み込み + 対角 SSM + スパース top-k アテンション）が深い transformer スタックを置き換え、トークンごとのソフトルーターがそれらを混合し、バイトトークナイザが語彙の出荷を回避します。興味深い主張はプリミティブ（すべて先行研究——BitNet、Mamba、top-k アテンション）ではなく——それは*組み合わせ、デプロイの物語、そして誠実な評価*であり、これがどこで勝ち（60K）どこで負けるか（944K）を示します。C エンジンはゼロヒープ、静的バッファ、決定的なメモリフットプリントです。

## エージェントが壊してはならないもの

これらは支えとなる不変条件です。完了を報告する前に、あらゆる変更をこれらに照らして検証してください。

1. **Python ↔ C のビット単位で厳密な一致。** 単一 forward の一致が製品そのものです。テスト：`tests/test_parity_with_c.py`、`tests/test_parity_multitoken.py`。モデルコード、エクスポート形式、または C カーネルを変更したら、それらを実行して依然として通ることを確認してください。
2. **C エンジンでのヒープ割り当てゼロ。** `c_engine/upstream/atome.c` は、コンパイル時 `ATOME_*` マクロでサイズ設定された静的バッファのみを使います。ここに `malloc`/`calloc`/`free` を決して導入しないでください。スタック上の配列は問題ありません。
3. **すべての `torch.load` で `weights_only=True`。** キットの全チェックポイントは `{"config": dict, "state_dict": dict}`——純粋なテンソル + プリミティブです。悪意ある .pt ファイルに対して `weights_only=False` で読み込むのは RCE です。これを退行させないでください。
4. **エクスポータにハードコードされたモデル定数を置かない。** `scripts/export_to_atome.py` はチェックポイントから `top_k`（およびすべての構成）を読み取り、実際の値を C ヘッダに書き込みます。定数をハードコードしないでください——`tests/test_export_format.py` に、それを捕まえる回帰テストがあります。
5. **`atome_predict_next` と `atome_generate` の境界チェック。** どちらも、あらゆるインデックス参照/memcpy の前に `n_tokens < 1`、`prompt_len < 1`、NULL ポインタを拒否します。これらを取り除かないでください——それらがなければ `state->x[n_tokens - 1]` は未定義動作（UB）です。
6. **公開された 3 つのチェックポイントのみを出荷。** `checkpoints/atome_944k.bin`、`checkpoints/atome_1m_v1.pt`、`checkpoints/vanilla_1m_v1.pt` は追跡され、`.gitignore` でホワイトリスト化されています。*新しい* `*.pt`/`*.atome*`/`*.bin` の成果物はすべて既定で git に無視されます——明示的なホワイトリスト項目と理由なしに、公開リリースにチェックポイントを追加しないでください。
7. **ベンチマークにおける誠実さ。** `HONEST_RESULTS.md` は勝利（60K パラメータで vanilla FP32 より困惑度が約 22 % 良い、同一フラッシュ予算で 52 % 良い）*と*敗北（944K 規模で vanilla が約 11 % 勝つ）の*両方*を記録します。要点をより良く聞こえさせるために、敗北を静かに落とさないでください。

## ファイルマップ

```
atome-llm-kit/
├── README.md              ← user-facing intro
├── PAPER.md               ← architecture writeup
├── HONEST_RESULTS.md      ← what works, what doesn't, costs
├── FRONTIER.md            ← what's still being explored
├── QUICKSTART.md          ← 30-min train + export walkthrough
├── REPRODUCE.md           ← how to reproduce the headline benchmarks
├── LICENSE / NOTICE       ← Apache 2.0 + attribution
│
├── atome_llm/             ← Python package
│   ├── core/
│   │   ├── atome_lm.py       — main model
│   │   ├── mcu_block.py      — 3-pathway block
│   │   ├── router.py         — per-token soft router
│   │   ├── ssm.py            — diagonal SSM
│   │   ├── sparse_attention.py — top-k attention
│   │   └── ternary*.py       — ternary weight modules
│   ├── tokenize.py         — byte tokenizer (no BPE)
│   └── baselines/          — vanilla FP32 transformer for A/B
│
├── c_engine/upstream/     ← The C99 inference engine
│   ├── atome.c               — implementation (~600 lines, zero heap)
│   └── atome.h               — public API + compile-time macros
│
├── scripts/
│   ├── train_demo.py         — quick training (~30 min CPU)
│   ├── export_to_atome.py    — checkpoint → .atome binary + C header
│   ├── demo.py               — interactive REPL
│   ├── evaluate.py           — bits-per-byte eval
│   └── run_ab_sweep.py       — 60K param-fair / flash-fair A/B
│
└── tests/                 ← 146 tests, all expected to pass
    ├── test_parity_with_c.py        — single-forward Python ↔ C
    ├── test_parity_multitoken.py    — multi-token Python ↔ C
    ├── test_qemu_parity.py          — host C ↔ QEMU ARM (skips if QEMU missing)
    ├── test_export_format.py        — binary format + header generation
    └── test_*.py                    — model shape, router, SSM, ternary, etc.
```

## 作業を検証する

```bash
# from repo root, after install.sh has run once
. .venv/bin/activate
pytest -q       # expect: 146 passed (or 145 + 1 skipped if no qemu-system-arm)
```

それが、完了を宣言する前に重要な唯一の信号です。`atome_llm/core/` または `c_engine/upstream/` の何かを変更したら、このステップを飛ばさないでください。

## エージェントがここでよく間違える点

- **C エンジンを定型コードとして扱う。** 違います——各行は RAM/フラッシュでサイズ設定されています。割り当てを追加せず、libc の依存を追加せず、`printf` を追加しないでください。要点のすべては、これがキロバイトの RAM を持つ 2 ドルのチップで動くことです。
- **スイープを再実行せずにドキュメント内のパラメータ数やベンチマーク数を「改善」しようとする。** `HONEST_RESULTS.md` の 60K / 944K / 22 % / 52 % / -11 % の数値は、具体的で再現可能な実行に結び付いています。再現できないなら、編集しないでください。
- **ML 風のフォールバックを追加する（「if state is None, do X」）。** ランタイムは決定的です——あらゆるコードパスが通ります。「起こるはずがない」分岐はありません。
- **バイトトークナイザを一般化する。** それは意図的に生バイトです。BPE や sentencepiece を追加すると語彙テーブル（数キロバイトのフラッシュ）を出荷することになり、設計を台無しにします。
- **実験的なアイデアを同梱する。** `c_engine/experiments/delta_inference/` は明示的に実験的です——サポートされる経路上になく、一致テストもされていません。一致 + 境界チェックのカバレッジなしに、実験を `c_engine/upstream/` に昇格させないでください。
- **「通すために」一致テストをいじる。** 一致テストが失敗するなら、間違っているのは*コード*であってテストではありません。Python/C の乖離を見つけてください——ほとんどの場合、畳み込みカーネルの向きの off-by-one、SSM 状態の初期化、または陳腐化したハードコード定数です。

## 何がオープンで何がそうでないか

| オープン（このリポジトリ、Apache 2.0）             | 非オープン（商用）                            |
|-----------------------------------------------------|-----------------------------------------------|
| アーキテクチャ、学習コード、C エンジン              | シリコンの立ち上げ（プラットフォーム別統合）  |
| 944K 学習済み重み（`checkpoints/atome_944k.bin`）   | Atome Secure Boot Pack（署名済み `.atome` blob）|
| PyTorch ソース `atome_1m_v1.pt` + vanilla ベースライン | プラットフォーム別ハードニング + 認証フロー |
| エクスポート形式 + 一致テスト                       | より大きな内部 V2 モデル（3M パラメータ、混合ドメイン）|
| サンプルデータ、A/B スイープのハーネス              | カスタムファインチューニング + 顧客別統合     |
| すべてのドキュメント（PAPER、HONEST_RESULTS 等）    | atomelm.com のマーケティング / ライブデモサイト |

アーキテクチャは設計上公開されており、学習コストは約 1〜2 ドルです——ライセンスを堀にする戦略は決して機能しなかったでしょうし、重みを堀にするのは薄かったでしょう。実際に防御可能な価値は、デプロイごとの統合作業、セキュリティのハードニング、そして専有として保たれるより大きな V2 モデルにあり——そのいずれもこのリポジトリには入っていません。

## さらに深く掘る必要があれば

- アーキテクチャの根拠：`PAPER.md`
- 何が測定され、何がされず、何にいくらかかったか：`HONEST_RESULTS.md`
- まだ探索中のもの：`FRONTIER.md`
- 要点の数値を再現する方法：`REPRODUCE.md`
- ゼロから学習・エクスポート済みモデルまでの行き方：`QUICKSTART.md`

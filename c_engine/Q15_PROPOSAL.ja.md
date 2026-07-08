[English](Q15_PROPOSAL.md) · [Français](Q15_PROPOSAL.fr.md) · [Español](Q15_PROPOSAL.es.md) · [简体中文](Q15_PROPOSAL.zh-CN.md) · [Deutsch](Q15_PROPOSAL.de.md) · **日本語** <!-- i18n-switcher -->

# Q15 活性化パス — 設計提案（未実装）

## これが存在する理由

5 月 10 日のエミュレータのセッションでは、当初 ARM のソフトフロートとホストの x86 の間の
浮動小数点演算順序がマルチトークンのドリフトを引き起こしていると疑いました。
調べたところ、実際の原因はロジックのバグでした——`atome_predict_next` が
`state->ssm_h` を決してリセットせず、以前の呼び出しの SSM 状態が後続の
forward パスを汚染していたのです。そのバグは現在修正され（`atome.c:294-300`）、
48/48 の QEMU トークンが Python と一致します。

しかし Q15 は依然、**性能とエネルギー**のために価値があります。正しさのためでは
ありません。本ファイルは、次のセッションが冷えた状態から拾い上げられるよう、
設計を凍結します。

## Q15 が得るもの（最善の見積もり、未測定）

| 利得 | 規模 | 理由 |
|---|---|---|
| M0 / M3 上の計算高速化 | ~5-10× | FPU なし；整数の積和は ARM v7-M で単一サイクル |
| M4F / M7 上の計算高速化 | ~1.5-2× | すでに FPU あり；利得は SIMD（`__SADD16`、`SMLAD`）から |
| BSS 削減 | ~40-50% | 活性化テンソルが半減（fp32 → int16） |
| トークンごとの電力 | ~3-5× 低下 | サイクル数に比例 |
| ホスト間の決定性 | 完全 | 整数演算が丸め順序の曖昧さを消す |

## Q15 が得ないもの

- より小さい `.atome` blob——重みはすでに三値（各 ~0.5 ビット）。
  活性化はフラッシュではなく RAM に存在します。
- より良いモデル品質——推論時の量子化は損失を伴い、困惑度は
  わずかに上がる見込み（校正すればおそらく <5 %；要測定）。

## 設計

### コンパイル時スイッチ

`ATOME_DTYPE` を追加し、`f32`（今日、既定）または `q15`（新規）を選択します。
フラグがなければ既存のテスト / ファームウェアは変更されません。

```c
#ifndef ATOME_DTYPE_Q15
#define ATOME_DTYPE_Q15 0
#endif

#if ATOME_DTYPE_Q15
typedef int16_t  atome_act_t;
typedef int32_t  atome_acc_t;
#else
typedef float    atome_act_t;
typedef float    atome_acc_t;
#endif
```

### 何が浮動小数点のままか

- LayerNorm（sqrt + 除算——Q15-LayerNorm は存在するが 200 LOC 追加する）
- Softmax（exp——同様）
- 単一のアテンションスケール `1.0 / sqrtf(d_h)`
- 最終 logits（argmax を曖昧にしないため）

これらはサイクルの <2 % です。境界で Q15 との間を変換します。

### 何が Q15 になるか

- すべての三値 matvec（`atome_ternary_matvec`）
- 因果畳み込み（`atome_causal_conv`）
- SSM の forward（注意深く——`tanh(a)` と `b * x` は固定小数点処理が必要）
- アテンションの内積（Q.K）
- アテンションの加重和（sum_i p_i * V_i）

### テンソルごとのスケール追跡

各 Q15 テンソルは暗黙のシフトを持ちます。現在のスケールを保持する小さな
ステップごとの `atome_q15_state_t` を維持し、その場で更新します：

```c
typedef struct {
    int x_shift;        /* current activation shift (Q15-pos) */
    int normed_shift;
    int path_local_shift;
    int path_ssm_shift;
    int path_attn_shift;
} atome_q15_state_t;
```

校正スクリプト（Python 側）：数千のプロンプトを浮動小数点モデルに通し、
層ごとの最大絶対活性化を記録し、99.9 パーセンタイルが [-32768, 32767] に
収まるようシフトを設定します。

### テスト計画

1. 新しい `tests/test_q15_parity.py`：浮動小数点参照 vs Q15 forward。
   許容差：d=64 でプロンプトの >95 % について top-1 logit が一致し、
   トークンごとのコサイン類似度 >0.98。
2. 新しい `c_engine/targets/cortex-m3-q15/` ターゲット。ファームウェアが
   トークンごとのサイクル数を報告；同一構成で `cortex-m3-gen` より 5-10× 高速を期待。
3. `RAM_TABLE.md` に `q15` の行を追加。期待：tinystories 構成が
   104 KB ピーク → 約 55 KB ピークに下がる。F103 Blue Pill（2-4 ドル）が学習済み
   モデルにとって到達可能になる。

## 見積もり工数

| フェーズ | 工数 | リスク |
|---|---|---|
| 校正（Python）+ スケールのエクスポート | 半日 | 低 |
| `atome.c` の Q15 パス（骨格 + matvec + conv） | 1 日 | 低 |
| SSM Q15（tanh テーブル + スケール済み積和） | 半日 | 中——数値的な注意 |
| アテンション Q15（Q·K、softmax 入力のスケーリング） | 半日 | 中 |
| テスト + ファームウェアターゲット | 半日 | 低 |
| 校正チューニング + ベンチマーク | 半日 | 低 |
| **合計** | **~3-4 日** | — |

## いつ再訪するか

以下の後で：
1. 1M パラメータのチェックポイント（`TRAIN_1M_RUNBOOK.md`）が到着し、速度/電力の
   最適化に値する実モデルを持つとき。
2. Nucleo-F411RE での実シリコン検証が、今日の QEMU の数字が予測的であることを
   確認したとき。
3. ユーザーが F103 Blue Pill（2-4 ドル）で Atome を実行したいとき——学習済みモデル
   構成で現在 RAM に阻まれている、最も安価な階層。

これは、きれいで、範囲が定まり、自己完結した作業の一片です。上記の条件の
1 つが満たされたら拾い上げてください。

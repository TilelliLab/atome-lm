[English](RELEASE_NOTES_v2.0.md) · [Français](RELEASE_NOTES_v2.0.fr.md) · [Español](RELEASE_NOTES_v2.0.es.md) · [简体中文](RELEASE_NOTES_v2.0.zh-CN.md) · [Deutsch](RELEASE_NOTES_v2.0.de.md) · **日本語** <!-- i18n-switcher -->

# Atome LM v2 — SuperESP（リリースノート）

**v2.0 — Atome 三値エンジン上の応用エッジ AI 層。** このリポジトリの `superesp/` 配下で
出荷され、`atome_llm.core` をインポートし `c_engine/upstream/atome.c` を使うため、
それが動作するエンジンと並んで存在します。

## 内容
- **11 の応用デバイス上ヘッド + OS ディスパッチャ**（分類）：agri、voice、
  motion、sound-scene、anomaly、air、os-telemetry、power/NILM、occupancy、wearable、
  water、forecast。加えて**回帰**ヘッド。
- **ユニバーサル ESP32 インストーラ**——チップを自動検出し、esp32 / s2 / s3 / c3 / c6 / h2
  （Xtensa + RISC-V）向けのビルド済みファームウェアを書き込みます。ユーザーに ESP-IDF は不要。
- **ライブセンサー農業ファームウェア**（土壌 ADC + DHT22 + リレー）。
- **自作ループ**：logger ファームウェア → `superesp log` → `train --csv` → `report` → `flashplan`。
- **信頼**：Ed25519 認証、ロード時の FNV 完全性チェック、改ざん検知可能な監査ログ、
  そして署名済みの**モデル動物園（model-zoo）**（`zoo build/list/pull/publish`、sha256 + 署名検証付き）。
- **CLI**：`superesp list / train / report / log / new / doctor / targets / setup / flashplan / zoo`。

## 検証済み（誠実）
- **実シリコン（ESP32-WROOM-32）で：12/12 アプリケーションが合格**、約 27 KB の状態、265 KB の空きヒープ。
- Python↔C のビット単位で厳密な一致（~1e-6）；6/6 ターゲットがビルド；SuperESP テスト 34/34；Atome 146/146（退行なし）。
- 留め置き：動作するヘッドは平均約 0.94。**Voice KWS = 0.625**（バンド化トークン化）——控えめで、
  三値アーキテクチャの上限にあります；誇張せず誠実に報告。
- **9 つのヘッドは物理に基づいた合成（SYNTHETIC）データで出荷、明確に明記。** `train --csv --name <head>`
  で任意のものをあなたの実データに差し替えられます。シリコンでテスト済みは esp32/WROOM のみ；他の 5 つはビルド+QEMU で検証済み。

## 堀（moat）ではない（率直に述べる）
本番グレードのオープンキット、すべて Apache-2.0——どの部品もコピー可能です。持続的な優位は
キーボードの外にあります：証明可能に最初であること、規制された垂直領域での認証、または動物園での採用。

## 予約（商用、本リリースには含まれない）
サービス（立ち上げ、認証/合規、パートナーシップ、ドメイン調整、ハードニング、ホワイトラベル）、
署名鍵の権威、ホスト型の動物園 + OTA、認証プログラム。
[atomelm.com/services](https://atomelm.com/services.html) を参照。

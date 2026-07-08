[English](RELEASE_NOTES_v2.0.md) · [Français](RELEASE_NOTES_v2.0.fr.md) · [Español](RELEASE_NOTES_v2.0.es.md) · **简体中文** · [Deutsch](RELEASE_NOTES_v2.0.de.md) · [日本語](RELEASE_NOTES_v2.0.ja.md) <!-- i18n-switcher -->

# Atome LM v2 — SuperESP（发布说明）

**v2.0 — Atome 三元引擎之上的应用化边缘 AI 层。** 在本仓库中随 `superesp/` 出货；
它导入 `atome_llm.core` 并使用 `c_engine/upstream/atome.c`，
因此它与其所运行的引擎并存。

## 它包含什么
- **11 个应用化的设备端头 + 一个 OS 分派器**（分类）：agri、voice、
  motion、sound-scene、anomaly、air、os-telemetry、power/NILM、occupancy、wearable、
  water、forecast。外加一个**回归**头。
- **通用 ESP32 安装器**——自动检测芯片，为 esp32 / s2 / s3 / c3 / c6 / h2
  （Xtensa + RISC-V）烧录预编译固件。用户无需 ESP-IDF。
- **实时传感器农业固件**（土壤 ADC + DHT22 + 继电器）。
- **做你自己的循环**：logger 固件 → `superesp log` → `train --csv` → `report` → `flashplan`。
- **信任**：Ed25519 认证、加载时 FNV 完整性检查、防篡改审计日志，
  以及一个签名的**模型库（model-zoo）**（`zoo build/list/pull/publish`，带 sha256 + 签名验证）。
- **CLI**：`superesp list / train / report / log / new / doctor / targets / setup / flashplan / zoo`。

## 已验证（诚实）
- **在真实硅片（ESP32-WROOM-32）上：12/12 个应用通过**，约 27 KB 状态，265 KB 空闲堆。
- Python↔C 逐位精确一致（~1e-6）；6/6 个目标构建；SuperESP 测试 34/34；Atome 146/146（无回归）。
- 留出：工作正常的头平均约 0.94。**Voice KWS = 0.625**（分带分词）——适中且
  处于三元架构上限；如实报告，未夸大。
- **9 个头以物理基础的合成（SYNTHETIC）数据出货，已清楚标注。** 通过 `train --csv --name <head>`
  用你的真实数据替换任意一个。只有 esp32/WROOM 经硅片测试；其余 5 个经构建+QEMU 验证。

## 不是护城河（moat）（直白说明）
生产级开放套件，全部 Apache-2.0——每一部分都可复制。持久的优势在
键盘之外：可证明地率先、受监管垂直领域的认证，或在库上的采用。

## 保留（商业，不在本次发布中）
服务（落地、认证/合规、合作、领域调优、加固、白标）、
签名密钥权威、托管的库 + OTA，以及认证计划。见
[atomelm.com/services](https://atomelm.com/services.html)。

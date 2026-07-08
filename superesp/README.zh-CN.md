[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · **简体中文** · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# SuperESP — 面向 ESP32 边缘的应用化 Atome-LM

SuperESP 把 Atome 微型三元（1.58 bit）模型变成一套**应用化的流式分类器**，
它们在微控制器上运行，*取代*文本生成，外加一个设备端的 **"OS" 运行时**，
读取 ESP32 的所有传感器并分派到正确的头（head）。

它实现了 2026-06-13 Atome 护城河（moat）评审中的 PIVOT #1：`atome_classify`
头在 C 引擎中已存在，但**从未被训练过**。SuperESP 训练它
——面向 7 个真实边缘任务——并接入 delta 推理（能量）、弃权
（不确定时拒答）以及加密认证（可审计性）。

## 11 个头（一次共享的引擎构建；每个头 = 一个不同的 ATOMECL01 blob）
| 头 | 任务 | 数据 |
|---|---|---|
| SuperESP-Agri | 土壤/气候 → 灌溉/霜冻/虫害/健康/故障 | SYNTH（农艺） |
| SuperESP-Voice | I2S 麦克风 → 农场语音命令（on/off/stop/go） | REAL（Speech Commands） |
| SuperESP-Motion | IMU → 活动/手势/跌倒 | REAL（UCI HAR） |
| SuperESP-Sound-Scene | 环境音频 → 声学事件 | SYNTH（合成音频） |
| SuperESP-Anomaly | 振动 → 机器健康 | SYNTH（物理） |
| SuperESP-Air | 气体+气候 → 空气质量/泄漏 | SYNTH（物理） |
| SuperESP-OS | 融合的 ESP32 遥测 → 设备状态 + 分派 | SYNTH（芯片遥测） |
| SuperESP-Power | 电流钳能量/NILM → 负载类型 | SYNTH（物理） |
| SuperESP-Occupancy | PIR+CO2+声音 → 房间占用 | SYNTH（物理） |
| SuperESP-Wearable | PPG+IMU → 心脏/活动状态（非医疗） | SYNTH（物理） |
| SuperESP-Water | 流量+压力+湿度 → 泄漏/淹水 | SYNTH（物理） |

## 速度
- **三元核：** 无分支的 4-trit/字节 matvec → **分类 306 µs → 87 µs（3.5×）**，主机上（-O3）约 11,400/s。
  惠及整个 Atome 引擎（classify + generate + ESP32）。逐位精确得以
  保持（一致性最大 |Δ| 8.3e-7）；现有的 146 个测试全部通过。
- **变化门控的流式处理**（`framework/streaming.py`）：在一个相关的、常开的流上，只在
  输入漂移越过一个发放阈值时才重新运行模型；否则复用缓存的
  决策（与逐帧运行逐位相同）。跳过率就是收益（静止流上 ≈98 %）。
- **Delta 推理**（`framework/delta.py`）：在相关流上 matvec 操作数少 4–11×。
- ESP32 硅片上的 tok/s/RAM **尚未测量**（无板子）；预期主机加速会延续。

关于留出精度、弃权 AURC、delta 推理加速以及每个头的 REAL/SYNTH
标签，见 `HONEST_RESULTS.md` / `artifacts/RESULTS.json`。

## 工作原理
- **分词器**（`framework/tokenize.py`）：每个传感器/特征帧被线性
  量化为一个字节序列（≤32）——因此现有的 256 字节词表的 Atome
  引擎无需改动即可运行。量化常量仅在 TRAIN 上拟合（无泄漏）。
- **模型**（`framework/model.py`）：现有的 `AtomeLM` 基座 + 一个在最后一个
  token 的 final-norm 隐藏态上的三元分类头——恰好就是 C 的
  `atome_classify` 所计算的。**Python↔C 逐位精确一致**（最大 |Δ| ~7e-7）。
- **弃权**（`framework/abstain.py`）：当 top1-top2 softmax 边距
  较低时拒答；以风险-覆盖曲线 + 相对 oracle/随机 的 AURC 报告。
- **Delta 推理**（`framework/delta.py`）：面向相关传感器流的积分-发放
  delta matvec——来自 delta_inference 实验的实测能量代理，
  逐头应用。
- **认证**（`attest/sign.py`）：Ed25519 签名的回执，绑定 sha256(blob)
  + 元数据，使部署者能证明*这个*确切的头运行过。防篡改（tamper-evident）。
- **运行时**（`runtime/dispatcher.py`）：按模态把一帧路由到它的头，
  在融合遥测上运行 OS 头，在故障状态下卸载负载。C 镜像：
  `c_engine/superesp/superesp_os.c`。固件骨架：`superesp/firmware/`。

## 安装
```
pip install -e .              # core (torch + numpy); run the CLI as: python3 -m superesp.cli <cmd>
pip install -e ".[superesp]"  # + cryptography/scipy/pyserial/esptool (attestation, audio, flashing)
```

## 烧录任意 ESP32（无需 ESP-IDF——为 esp32/s2/s3/c3/c6/h2 预编译）
```
bash superesp/esp32/install.sh    # auto-detects the chip, flashes the matching
                                  # prebuilt firmware, runs all heads, writes a report
```

## 几分钟内做出你自己的分类器（无需 ML 技能——记录→训练→烧录的循环）
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
**这 9 个 SYNTH 头只是默认值——完全可替换。** 用你自己的数据在一个内置
名称下训练，即可把它替换为一个真实世界的模型：
`python3 -m superesp.cli train --csv my_field.csv --name agri` 会覆盖合成 `agri`
头的 blob。没有任何东西是硬编码的；每个头都是"在数据上训练 → 导出一个 blob"。

## 复现 / 使用你自己的数据
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
任何拥有自己 ESP32 传感器窗口 CSV 的人都能得到一个逐位精确、可认证的
设备端分类器——无需 ML 搭建。这是商业 TinyML 流水线的
开放/可审计对应物。

## 诚实范围 / 护城河（moat）
各个头是真实的应用化边缘 AI（一个步骤 / 一个产品），**而非护城河**——
TinyML 的 KWS/手势/异常已很拥挤（TFLite-Micro、Edge Impulse）。唯一
可防御的角度是**超微三元 + 逐位可审计 + 加密认证 +
delta 高效**这一组合，作为一个统一的设备端 OS。那是一个
先发/集成的赌注，而非沙盒护城河。用 SYNTH 数据训练的头
是物理风格的替身，并如此标注——不是现场部署主张。硅片上的
吞吐量/RAM **尚未测量**（无板子）。
```
```

[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · **简体中文** · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# SuperESP 固件骨架（ESP32 / ESP-IDF）

> **状态：仅构建的骨架——未烧录，未在硅片上测量。**
> 这台机器没有物理 ESP32，也没有 ESP-IDF 工具链。下面的固件
> 是真实的结构（它复用内置（vendored）的 `atome.c`/`atome.h` 引擎和
> 训练好的 ATOMECL01 头 blob），但板上的 tok/s、RAM 高水位以及
> 实时 ADC/I2S 捕获**在此未测量**。主机侧的 C 分派器
> `c_engine/superesp/superesp_os.c` *确实*被编译并测试（见 superesp 测试）。

## 它做什么（"OS"的想法）
上电时，固件：
1. 把 ESP32 自身的遥测——`esp_get_free_heap_size()`、内部温度
   传感器、Wi-Fi RSSI、ADC 通道、hall、touch——读入 **OS 融合帧**。
2. 把该帧量化为字节（使用从 `os_telem.tok.json` 烘焙的逐特征
   `vmin/vmax`），并用 **OS 头**运行 `atome_classify` 以得到一个
   设备状态（normal / low_memory / overheating / wifi_degraded / power_fault）。
3. 应用负载卸载策略（例如在过热时禁用音频头），然后读取
   活动传感器（agri 用 ADC，voice 用 I2S 麦克风）
   并把该帧分派到它的头——在不确定时弃权。

于是 Atome 作为设备监督者运行，而非文本生成器。全部 7 个头共享
一次引擎构建（同一共享配置）；每个头是一个不同的嵌入式 blob。

## 构建（在有 ESP-IDF + 一块板子的机器上）
```
idf.py set-target esp32
idf.py build            # compile-time config in main/CMakeLists.txt
idf.py -p /dev/ttyUSB0 flash monitor
```
编译期定义（d_model=32、n_layers=2、...）必须与导出这些 blob 时所用的
SuperESP 共享配置（superesp/framework/config.py）相匹配。

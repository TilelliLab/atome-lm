# SuperESP — applied Atome-LM for the ESP32 edge

SuperESP turns the Atome tiny ternary (1.58-bit) model into a suite of **applied
streaming classifiers** that run on a microcontroller *instead of* text
generation, plus an on-device **"OS" runtime** that reads all the ESP32's
sensors and dispatches to the right head.

It realizes PIVOT #1 of the 2026-06-13 Atome moat review: the `atome_classify`
head existed in the C engine but had **never been trained**. SuperESP trains it
— for 7 real edge tasks — and wires in delta-inference (energy), abstention
(refuse-when-unsure), and cryptographic attestation (auditability).

## The 11 heads (one shared engine build; each head = a different ATOMECL01 blob)
| head | task | data |
|---|---|---|
| SuperESP-Agri | soil/climate → irrigate/frost/pest/healthy/fault | SYNTH (agronomic) |
| SuperESP-Voice | I2S mic → farm voice commands (on/off/stop/go) | REAL (Speech Commands) |
| SuperESP-Motion | IMU → activity/gesture/fall | REAL (UCI HAR) |
| SuperESP-Sound-Scene | ambient audio → acoustic event | SYNTH (synth audio) |
| SuperESP-Anomaly | vibration → machine health | SYNTH (physics) |
| SuperESP-Air | gas+climate → air quality/leak | SYNTH (physics) |
| SuperESP-OS | fused ESP32 telemetry → device state + dispatch | SYNTH (chip telemetry) |
| SuperESP-Power | CT-clamp energy/NILM → load type | SYNTH (physics) |
| SuperESP-Occupancy | PIR+CO2+sound → room occupancy | SYNTH (physics) |
| SuperESP-Wearable | PPG+IMU → heart/activity state (not medical) | SYNTH (physics) |
| SuperESP-Water | flow+pressure+moisture → leak/flood | SYNTH (physics) |

## Speed
- **Ternary kernel:** branchless 4-trits/byte matvec → **classify 306 µs → 87 µs (3.5×)**, ~11,400/s
  on host (-O3). Benefits the whole Atome engine (classify + generate + ESP32). Bit-exact
  preserved (parity max |Δ| 8.3e-7); all 146 existing tests pass.
- **Change-gated streaming** (`framework/streaming.py`): on a correlated always-on stream, only
  re-run the model when the input drifts past a firing threshold; otherwise reuse the cached
  decision (bit-identical to running every frame). Skip-rate is the win (≈98% on a static stream).
- **Delta-inference** (`framework/delta.py`): 4–11× fewer matvec ops on correlated streams.
- On-silicon ESP32 tok/s/RAM **NOT MEASURED** (no board); host speedups expected to carry.

See `HONEST_RESULTS.md` / `artifacts/RESULTS.json` for held-out accuracy,
abstention AURC, delta-inference speedup, and the REAL/SYNTH label per head.

## How it works
- **Tokenizer** (`framework/tokenize.py`): each sensor/feature frame is linearly
  quantized to a sequence of bytes (≤32) — so the existing 256-byte-vocab Atome
  engine runs unchanged. Quantization constants are fit on TRAIN only (leak-free).
- **Model** (`framework/model.py`): the existing `AtomeLM` base + a ternary
  classification head over the last token's final-norm hidden — exactly what the
  C `atome_classify` computes. **Bit-exact Python↔C parity** (max |Δ| ~7e-7).
- **Abstention** (`framework/abstain.py`): refuse when the top1-top2 softmax
  margin is low; reported as a risk-coverage curve + AURC vs oracle/random.
- **Delta-inference** (`framework/delta.py`): integrate-and-fire delta matvec for
  correlated sensor streams — the measured energy proxy from the delta_inference
  experiment, applied per head.
- **Attestation** (`attest/sign.py`): Ed25519-signed receipt binding sha256(blob)
  + metadata, so a deployer can prove THIS exact head ran. Tamper-evident.
- **Runtime** (`runtime/dispatcher.py`): route a frame to its head by modality,
  run the OS head on fused telemetry, shed load under fault states. C mirror:
  `c_engine/superesp/superesp_os.c`. Firmware skeleton: `superesp/firmware/`.

## Install
```
pip install -e .            # exposes the `superesp` command (or: python3 -m superesp.cli)
pip install -e .[esp32]     # + esptool/pyserial to flash a real board
```

## Flash any ESP32 (no ESP-IDF needed — prebuilt for esp32/s2/s3/c3/c6/h2)
```
bash superesp/esp32/install.sh    # auto-detects the chip, flashes the matching
                                  # prebuilt firmware, runs all heads, writes a report
```

## Make your OWN classifier in minutes (no ML skill — the log→train→flash loop)
```
# 1. flash the data-logger, then record YOUR sensor in each state:
superesp log --label dry   --out field.csv      # leave probe in dry soil
superesp log --label wet   --out field.csv      # ...then wet soil
# 2. train + see how good it is + deploy:
superesp train  --csv field.csv --name myfarm
superesp report myfarm                          # confusion matrix + abstention (md + html)
superesp flashplan myfarm
# (or start from a blank template:)  superesp new myfarm --features 30
```
**The 9 SYNTH heads are just defaults — fully swappable.** Train under a built-in
name with your own data to replace it with a real-world model:
`superesp train --csv my_field.csv --name agri` overwrites the synthetic `agri`
head's blob. Nothing is hard-coded; every head is "train on data → export blob".

## Reproduce / bring your own data
```
python3 -m superesp.cli list                      # the 11 built-in heads
python3 -m superesp.cli train agri                # train+eval+export one built-in head
# YOUR sensor: rows = up to 32 features + a label column
python3 -m superesp.cli train --csv my.csv --label-col state --name mysensor
python3 -m superesp.cli flashplan mysensor        # how to bake the blob into firmware
# or everything at once:
python3 -m superesp.train_all && python3 -m superesp.attest_all
python3 -m pytest superesp/tests                  # 20 tests: framework, parity(gcc), attest, dispatch, streaming, csv, novelty
```
Anyone with a CSV of their own ESP32 sensor windows gets a bit-exact, attestable
on-device classifier — no ML setup. This is the open/auditable analogue of a
commercial TinyML pipeline.

## Honest scope / moat
The individual heads are real applied edge-AI (a STEP / product), **not moats** —
TinyML KWS/gesture/anomaly are crowded (TFLite-Micro, Edge Impulse). The only
defensible angle is the **ultra-tiny ternary + bit-exact-auditable +
cryptographically-attested + delta-efficient** combination as a unified
on-device OS. That is a first-mover/integration bet, not a sandbox moat. Heads
trained on SYNTH data are physics-style stand-ins, labeled as such — not
field-deployment claims. On-silicon throughput/RAM are **NOT MEASURED** (no board).
```
```

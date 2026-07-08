[English](QUICKSTART.md) · [Français](QUICKSTART.fr.md) · [Español](QUICKSTART.es.md) · [简体中文](QUICKSTART.zh-CN.md) · **Deutsch** · [日本語](QUICKSTART.ja.md) <!-- i18n-switcher -->

# Atome LM — Schnellstart

Der 60-Sekunden-Pfad vom Klon zu einem trainierten, Mikrocontroller-fertigen Modell.
Für die vollständige Geschichte siehe [README.md](README.de.md) und [REPRODUCE.md](REPRODUCE.de.md).

## 1. Installieren (nur CPU, keine GPU)

```bash
./install.sh
. .venv/bin/activate
```

`install.sh` erstellt ein lokales `.venv`, installiert CPU-only-PyTorch und Atome
LM und führt `check_env.py` aus. Führe `python check_env.py` jederzeit erneut aus, um
die Umgebung erneut zu verifizieren.

## 2. Ein winziges Demo-Modell trainieren

Eine ~256 KB große Probe des freizügig lizenzierten TinyStories-Korpus wird in
`data/sample.txt` ausgeliefert, sodass dies offline läuft:

```bash
python scripts/train_demo.py --data data/sample.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

Für einen größeren Korpus hole einen mit dem mitgelieferten Builder:

```bash
python scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt
```

## 3. Mit ihm sprechen

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
```

Die REPL gibt die Fortsetzung plus die Router-Entropie-Balken pro Schicht aus — das
kostenlose Unsicherheitssignal pro Token.

## 4. Export auf einen Mikrocontroller

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome --header
```

In der Standardkonfiguration liegt das `.atome`-Binary deutlich unter 100 KB. Lege den
generierten `.h` in ein C-Projekt und lade es mit der Engine in
`c_engine/`.

## 5. Die Tests ausführen

```bash
pytest -q
```

Die QEMU-Cortex-M3-Paritätstests brauchen `qemu-system-arm`, `arm-none-eabi-gcc`
und `xxd` im `PATH`; sie werden **übersprungen** (skipped, nicht fehlgeschlagen), wenn die
Toolchain fehlt.

---

**Trainierte Gewichte sind mitgeliefert** in `checkpoints/` — `atome_944k.bin`
(gepackter C-Engine-Blob), `atome_1m_v1.pt` (PyTorch-Quelle) und
`vanilla_1m_v1.pt` (FP32-Baseline für das 944 K-Umkehrungs-A/B in
[HONEST_RESULTS.md](HONEST_RESULTS.de.md)). Wenn du das Modell
ohne vorheriges Training ausführen möchtest:

```bash
python scripts/demo.py --checkpoint checkpoints/atome_1m_v1.pt
```

Wenn du dein eigenes von Grund auf trainieren möchtest, folge dem
`scripts/train_demo.py`-Ablauf oben — er erzeugt ein 60 K-Parameter-Modell
in ~30 Min. auf einer CPU.

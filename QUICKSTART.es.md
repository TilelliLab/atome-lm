[English](QUICKSTART.md) · [Français](QUICKSTART.fr.md) · **Español** · [简体中文](QUICKSTART.zh-CN.md) · [Deutsch](QUICKSTART.de.md) · [日本語](QUICKSTART.ja.md) <!-- i18n-switcher -->

# Atome LM — Inicio rápido

La ruta de 60 segundos del clon a un modelo entrenado y listo para microcontrolador.
Para la historia completa véase [README.md](README.es.md) y [REPRODUCE.md](REPRODUCE.es.md).

## 1. Instalar (solo CPU, sin GPU)

```bash
./install.sh
. .venv/bin/activate
```

`install.sh` crea un `.venv` local, instala PyTorch solo-CPU y Atome
LM, y ejecuta `check_env.py`. Reejecuta `python check_env.py` en cualquier momento para
reverificar el entorno.

## 2. Entrenar un modelo de demo minúsculo

Se envía una muestra de ~256 KB del corpus TinyStories con licencia permisiva en
`data/sample.txt`, de modo que esto corre sin conexión:

```bash
python scripts/train_demo.py --data data/sample.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

Para un corpus mayor, descarga uno con el constructor incluido:

```bash
python scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt
```

## 3. Háblale

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
```

El REPL imprime la continuación más las barras de entropía del enrutador por capa — la
señal de incertidumbre por token expuesta gratis.

## 4. Exportar a un microcontrolador

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome --header
```

Con la configuración por defecto, el binario `.atome` está muy por debajo de 100 KB. Deja el
`.h` generado en un proyecto C y cárgalo con el motor de
`c_engine/`.

## 5. Ejecutar los tests

```bash
pytest -q
```

Los tests de paridad QEMU Cortex-M3 necesitan `qemu-system-arm`, `arm-none-eabi-gcc`
y `xxd` en el `PATH`; se **omiten** (skipped, no fallan) cuando la cadena de
herramientas está ausente.

---

**Los pesos entrenados vienen incluidos** en `checkpoints/` — `atome_944k.bin`
(blob empaquetado del motor C), `atome_1m_v1.pt` (fuente PyTorch) y
`vanilla_1m_v1.pt` (referencia FP32 para el A/B de reversión en 944 K en
[HONEST_RESULTS.md](HONEST_RESULTS.es.md)). Si quieres ejecutar el modelo
sin entrenar primero:

```bash
python scripts/demo.py --checkpoint checkpoints/atome_1m_v1.pt
```

Si quieres entrenar el tuyo desde cero, sigue el
flujo de `scripts/train_demo.py` de arriba — produce un modelo de 60 K parámetros
en ~30 min en una CPU.

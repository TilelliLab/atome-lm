[English](CONTRIBUTING.md) · [Français](CONTRIBUTING.fr.md) · [Español](CONTRIBUTING.es.md) · [简体中文](CONTRIBUTING.zh-CN.md) · **Deutsch** · [日本語](CONTRIBUTING.ja.md) <!-- i18n-switcher -->

# Beitragen zu Atome LM

Danke, dass du einen Beitrag in Erwägung ziehst. Dies ist ein kleines, fokussiertes Projekt — ein winziges ternäres Sprachmodell + eine C99-Inferenz-Engine, die bit-genau mit ihm spricht. Lies zuerst `PROJECT_CONTENT.md`; es behandelt, was du nicht brechen darfst.

## Schnellstart

```bash
git clone https://github.com/TilelliLab/atome-lm
cd atome-lm
./install.sh
. .venv/bin/activate
pytest -q        # expect: 146 passed (or 145 + 1 skipped without qemu-system-arm)
```

## Bugs melden

Öffne ein Issue auf GitHub mit:

- was du ausgeführt hast (exakter Befehl)
- was du erwartet hast
- was passiert ist (vollständiger Fehler, nicht paraphrasiert)
- deine Plattform: OS, Python-Version und `python -c "import torch; print(torch.__version__)"`

Falls du auf einen Paritätsfehler stößt (Python-Forward ≠ C-Forward), hänge bitte den fehlschlagenden Seed und jeden von dir trainierten Checkpoint an — das sind die Bugs mit höchster Priorität.

## Einen Pull Request einreichen

1. Forke das Repo und erstelle einen Branch von `main`.
2. Mache deine Änderung.
3. Führe die vollständige Test-Suite aus — jeder PR muss `pytest -q` grün halten.
4. Falls deine Änderung `atome_llm/core/`, `c_engine/upstream/` oder das Exportformat berührt, **bestätige ausdrücklich**, dass diese Tests weiterhin bestehen:
   - `tests/test_parity_with_c.py` — Single-Forward-Python-↔-C-Parität
   - `tests/test_parity_multitoken.py` — Multi-Token-Python-↔-C-Parität
   - `tests/test_export_format.py` — Binärformat + Header-Generierung
5. Öffne den PR. Die CI führt die Suite auf Python 3.10 / 3.11 / 3.12 erneut aus.

## Umfang akzeptabler Änderungen

Willkommen:

- Bugfixes
- Neue Testabdeckung (besonders Fuzz-Fälle am C-Parser und Grenzeingaben an `atome_predict_next` / `atome_generate`)
- Performance-Verbesserungen, die die bit-genaue Parität wahren
- Dokumentations-Korrekturen und -Klärungen
- Neue MCU-Zielboards unter `c_engine/targets/`, *solange sie die Upstream-Engine nicht ändern*
- Neue Baselines unter `atome_llm/baselines/` für einen ehrlichen A/B-Vergleich

Außerhalb des Umfangs, bitte öffne keine PRs für diese:

- Heap-Allokation, dynamischen Speicher oder libc-Abhängigkeiten zu `c_engine/upstream/` hinzufügen
- "Sollte nicht passieren"-Fallbacks zu deterministischen Codepfaden hinzufügen
- Neue Tokenizer bündeln (BPE / sentencepiece) — der Byte-Tokenizer ist eine tragende Designentscheidung für das MCU-Flash-Budget
- Änderungen, die die Python-↔-C-Parität brechen, selbst wenn sie einen Benchmark verbessern
- Neue Features, die Code von `c_engine/experiments/` nach `c_engine/upstream/` befördern, ohne vollständige Paritäts- + Grenzprüfungs-Abdeckung

## Coding-Standards

- Python: halte es einfach, keine Hilfsschichten, keine Dekoratoren-für-Stil. Passe dich der bestehenden Stimme an — kleine Funktionen, keine verfrühte Abstraktion, Kommentare nur, wenn das *Warum* nicht offensichtlich ist.
- C: nur C99, keine GNU-Erweiterungen, keine libc über `<string.h>` / `<math.h>` / `<stdint.h>` hinaus. Statische Puffer, dimensioniert durch Kompilierzeit-`ATOME_*`-Makros. Grenzprüfung aller öffentlichen API-Eingaben.

## Sicherheit

Falls du ein Sicherheitsproblem findest (alles, was einem bösartigen Checkpoint oder `.atome`-Blob erlaubt, einen Host zu kompromittieren, der die Engine ausführt), sende bitte eine E-Mail an **hello@atomelm.com**, statt ein öffentliches Issue einzureichen. Wir koordinieren die Offenlegung.

## Lizenz

Durch das Einreichen eines Beitrags stimmst du zu, dass er unter der Apache License 2.0 (der Projektlizenz — siehe `LICENSE`) veröffentlicht wird.

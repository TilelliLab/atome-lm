#!/usr/bin/env bash
# =====================================================================
# install.sh — UNIVERSAL SuperESP installer for ANY ESP32 variant.
# Detects the chip, picks the matching prebuilt firmware, flashes it with
# esptool (no ESP-IDF needed by you), runs all apps on-chip, writes a report.
#
#     bash superesp/esp32/install.sh            # auto-detect + flash + test
#     TARGET=esp32c3 bash .../install.sh         # force a target
#
# Per-chip flash offsets (e.g. bootloader at 0x0 on S3/C3/C6/H2 vs 0x1000 on
# ESP32/S2) are read from each target's flasher_args.json — never hardcoded.
# NO `set -e`: never exits silently; every failure prints why + is saved to
# nocopypaste/last_run.txt (via t.sh).
# =====================================================================
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PRE="$HERE/prebuilt"
grn=$'\e[32m'; yel=$'\e[33m'; red=$'\e[31m'; cyn=$'\e[36m'; z=$'\e[0m'
hdr(){ printf '\n%s== %s ==%s\n' "$cyn" "$*" "$z"; }
warn(){ printf '%s! %s%s\n' "$yel" "$*" "$z"; }
die(){ printf '%s✗ %s%s\n' "$red" "$*" "$z" >&2; exit 1; }
PORT="${PORT:-}"; CAPTURE_S="${CAPTURE_S:-60}"; BAUD="${ESPTOOL_BAUD:-460800}"
find_port(){ [ -n "$PORT" ] && { echo "$PORT"; return 0; }
  for p in /dev/ttyACM* /dev/ttyUSB*; do [ -e "$p" ] && { echo "$p"; return 0; }; done; return 1; }

hdr "doctor"
command -v python3 >/dev/null 2>&1 || die "python3 not found."
ESPTOOL=""; for c in "esptool.py" "esptool" "python3 -m esptool"; do
  if $c version >/dev/null 2>&1; then ESPTOOL="$c"; break; fi; done
if [ -z "$ESPTOOL" ]; then warn "installing esptool..."
  python3 -m pip install --user --quiet esptool >/dev/null 2>&1 \
    || python3 -m pip install --user --quiet --break-system-packages esptool >/dev/null 2>&1
  for c in "esptool.py" "esptool" "python3 -m esptool"; do
    if $c version >/dev/null 2>&1; then ESPTOOL="$c"; break; fi; done; fi
[ -n "$ESPTOOL" ] || die "esptool unavailable. Install: pipx install esptool"
python3 -c "import serial" >/dev/null 2>&1 || python3 -m pip install --user --quiet pyserial >/dev/null 2>&1 \
  || python3 -m pip install --user --quiet --break-system-packages pyserial >/dev/null 2>&1
if PORT="$(find_port)"; then echo "${grn}esptool ok, port=$PORT${z}"; else
  die "no /dev/ttyUSB*/ttyACM* — plug the board in with a DATA cable, or pass PORT=/dev/ttyUSB0."; fi

hdr "detect chip"
INFO="$($ESPTOOL --port "$PORT" --before default_reset --no-stub flash_id 2>&1)"
echo "$INFO" | grep -iE "Chip is|flash size|MAC" || true
TARGET="${TARGET:-}"
if [ -z "$TARGET" ]; then
  chipline="$(echo "$INFO" | grep -i 'Chip is' | head -1)"
  case "$chipline" in
    *ESP32-S2*) TARGET=esp32s2 ;; *ESP32-S3*) TARGET=esp32s3 ;;
    *ESP32-C3*) TARGET=esp32c3 ;; *ESP32-C6*) TARGET=esp32c6 ;;
    *ESP32-H2*) TARGET=esp32h2 ;; *ESP32*)    TARGET=esp32 ;;
    *) die "could not identify chip from: '$chipline'. Force it: TARGET=esp32c3 bash $0" ;;
  esac
fi
echo "${grn}target=$TARGET${z}"
DIR="$PRE/$TARGET"
[ -d "$DIR" ] && [ -f "$DIR/flasher_args.json" ] || \
  die "no prebuilt firmware for '$TARGET' in $DIR. Available: $(ls "$PRE" 2>/dev/null | tr '\n' ' ')
  (ask me to build it, or install ESP-IDF and use run_battery.sh)."

hdr "flash $TARGET (esptool --no-stub; per-chip offsets from flasher_args.json)"
# Emit "<offset> <file>" pairs from flasher_args.json, mapping to our flat prebuilt files.
PAIRS="$(python3 - "$DIR" <<'PY'
import json,sys,os
d=sys.argv[1]; fa=json.load(open(os.path.join(d,"flasher_args.json")))
ff=fa.get("flash_files",{})
out=[]
for off,path in sorted(ff.items(), key=lambda kv:int(kv[0],16)):
    f=os.path.join(d, os.path.basename(path))
    if os.path.exists(f): out.append(off); out.append(f)
print(" ".join(out))
PY
)"
[ -n "$PAIRS" ] || die "could not read flash offsets from $DIR/flasher_args.json"
$ESPTOOL --chip "$TARGET" --port "$PORT" --baud "$BAUD" --before default_reset --after hard_reset \
  --no-stub write_flash $PAIRS
[ $? -eq 0 ] || die "flash failed on $PORT ($TARGET).
  - hold BOOT, tap EN/RESET, release BOOT, re-run
  - lower baud:  ESPTOOL_BAUD=115200 bash $0
  - wrong port:  PORT=/dev/ttyUSB0 bash $0"

hdr "capture serial (~${CAPTURE_S}s)"
mkdir -p "$HERE/reports" 2>/dev/null; chmod -R u+rwX "$HERE/reports" 2>/dev/null
LOG="$HERE/reports/serial_${TARGET}_$(date +%Y%m%d_%H%M%S).log"
( cd "$REPO" && python3 -m superesp.esp32.capture "$PORT" "$LOG" "$CAPTURE_S" ) \
  || warn "capture hiccup — if empty, use any serial monitor @115200."

hdr "grade -> per-application report"
if [ -s "$LOG" ]; then
  ( cd "$REPO" && python3 -m superesp.esp32.parse_report "$LOG" ) || warn "parse failed; raw: $LOG"
  echo "${grn}done ($TARGET). Report: superesp/esp32/reports/REPORT.md${z}"
else
  warn "no serial captured, but firmware IS flashed ($TARGET). Tell me and I'll read what landed."
fi

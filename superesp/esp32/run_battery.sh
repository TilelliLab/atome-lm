#!/usr/bin/env bash
# =====================================================================
# run_battery.sh — test ALL SuperESP apps on a real ESP32, save reports.
# Two flash paths (auto-chosen): ESP-IDF if present, else PREBUILT bins +
# esptool (lightweight — no 2GB IDF needed; the bins are built in the repo).
# NO `set -e` — never exits silently; every failure prints why.
# Env: PORT=/dev/ttyUSB0  TARGET=esp32  CAPTURE_S=60  ESPTOOL_BAUD=460800
# =====================================================================
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
FW="$HERE/firmware"; PRE="$HERE/prebuilt"
grn=$'\e[32m'; yel=$'\e[33m'; red=$'\e[31m'; cyn=$'\e[36m'; z=$'\e[0m'
hdr(){ printf '\n%s== %s ==%s\n' "$cyn" "$*" "$z"; }
warn(){ printf '%s! %s%s\n' "$yel" "$*" "$z"; }
die(){ printf '%s✗ %s%s\n' "$red" "$*" "$z" >&2; exit 1; }
PORT="${PORT:-}"; TARGET="${TARGET:-esp32}"; CAPTURE_S="${CAPTURE_S:-60}"; BAUD="${ESPTOOL_BAUD:-460800}"
find_port(){ [ -n "$PORT" ] && { echo "$PORT"; return 0; }
  for p in /dev/ttyACM* /dev/ttyUSB*; do [ -e "$p" ] && { echo "$p"; return 0; }; done; return 1; }

hdr "doctor"
command -v python3 >/dev/null 2>&1 || die "python3 not found."
# esptool (small) — auto-install if missing; it's all we need to flash prebuilt bins.
ESPTOOL=""; for c in "esptool.py" "esptool" "python3 -m esptool"; do
  if $c version >/dev/null 2>&1; then ESPTOOL="$c"; break; fi; done
if [ -z "$ESPTOOL" ]; then
  warn "installing esptool (lightweight)..."
  python3 -m pip install --user --quiet esptool >/dev/null 2>&1 \
    || python3 -m pip install --user --quiet --break-system-packages esptool >/dev/null 2>&1
  for c in "esptool.py" "esptool" "python3 -m esptool"; do
    if $c version >/dev/null 2>&1; then ESPTOOL="$c"; break; fi; done
fi
# pyserial for serial capture (also small)
python3 -c "import serial" >/dev/null 2>&1 || {
  python3 -m pip install --user --quiet pyserial >/dev/null 2>&1 \
    || python3 -m pip install --user --quiet --break-system-packages pyserial >/dev/null 2>&1; }
# IDF only if you happen to have it (optional)
HAVE_IDF=0; command -v idf.py >/dev/null 2>&1 && HAVE_IDF=1
[ -n "$ESPTOOL" ] && echo "${grn}esptool: $($ESPTOOL version 2>/dev/null | head -1)${z}" \
  || warn "esptool still missing (try: pipx install esptool)."
[ $HAVE_IDF -eq 1 ] && echo "${grn}idf.py present (will build fresh)${z}" || echo "no ESP-IDF — using prebuilt bins."
if PORT="$(find_port)"; then echo "${grn}port=$PORT target=$TARGET${z}"; else
  die "no /dev/ttyUSB*/ttyACM* — plug the board in with a DATA cable, or pass PORT=/dev/ttyUSB0."; fi
[ -r "$PORT" ] || warn "no read access to $PORT — if flash fails: sudo usermod -aG dialout \$USER (re-login)."

# --- choose binaries ------------------------------------------------
BOOT=""; PART=""; APP=""
if [ $HAVE_IDF -eq 1 ]; then
  hdr "build (idf)"
  ( cd "$FW" && idf.py set-target "$TARGET" && idf.py build ) && {
    BOOT="$FW/build/bootloader/bootloader.bin"; PART="$FW/build/partition_table/partition-table.bin"
    APP="$FW/build/superesp_battery.bin"; }
fi
if [ -z "$APP" ] || [ ! -f "$APP" ]; then
  hdr "prebuilt firmware"
  BOOT="$PRE/bootloader.bin"; PART="$PRE/partition-table.bin"; APP="$PRE/superesp_battery.bin"
  [ -f "$APP" ] && echo "${grn}using prebuilt: $(basename "$APP") ($(stat -c%s "$APP") B)${z}" \
    || die "no prebuilt bins in $PRE and no IDF build — ask me to rebuild."
fi

hdr "flash (esptool, --no-stub: the apt esptool ships a broken stub — same fix atome.sh used)"
[ -n "$ESPTOOL" ] || die "esptool not available to flash. Install: pipx install esptool"
$ESPTOOL --chip esp32 --port "$PORT" --baud "$BAUD" --before default_reset --after hard_reset \
  --no-stub write_flash -z 0x1000 "$BOOT" 0x8000 "$PART" 0x10000 "$APP"
[ $? -eq 0 ] || die "flash failed on $PORT.
  - hold BOOT, tap EN/RESET, release BOOT, re-run:  bash t.sh
  - lower baud:  ESPTOOL_BAUD=115200 bash t.sh
  - wrong port:  PORT=/dev/ttyUSB0 bash t.sh"

hdr "capture serial (~${CAPTURE_S}s)"
mkdir -p "$HERE/reports"; LOG="$HERE/reports/serial_$(date +%Y%m%d_%H%M%S).log"
( cd "$REPO" && python3 -m superesp.esp32.capture "$PORT" "$LOG" "$CAPTURE_S" ) \
  || warn "capture hiccup — if empty, run:  $ESPTOOL --port $PORT read flash isn't it; use any serial monitor @115200."

hdr "grade -> per-application report"
if [ -s "$LOG" ]; then
  ( cd "$REPO" && python3 -m superesp.esp32.parse_report "$LOG" ) || warn "parse failed; raw log: $LOG"
  echo "${grn}done. Report: superesp/esp32/reports/REPORT.md${z}"
else
  warn "no serial captured, but firmware IS flashed. Tell me and I'll read whatever landed."
fi

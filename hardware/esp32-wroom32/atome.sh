#!/usr/bin/env bash
# =====================================================================
# atome.sh — detect an ESP32, analyse it, and flash it with Atome.
#
#   ./atome.sh detect           find the board + read chip/flash/MAC
#   ./atome.sh analyze          recommend model config for this board
#   ./atome.sh doctor           check host toolchain (esptool / ESP-IDF)
#   ./atome.sh build [--toy]    build firmware (default = 944K model)
#   ./atome.sh flash            flash firmware to the board
#   ./atome.sh monitor          open the serial monitor
#   ./atome.sh all              detect -> analyze -> build -> flash -> monitor
#   ./atome.sh clean            remove the build dir
#
# Env overrides:  PORT=/dev/ttyUSB0   TARGET=esp32s3
# Runs on YOUR Ubuntu machine (the board is not visible from anywhere else).
# =====================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FW="$HERE/firmware"
MAIN="$FW/main"
STATE="$HERE/.atome_state"          # caches detected PORT/TARGET/PSRAM

c_red=$'\e[31m'; c_grn=$'\e[32m'; c_yel=$'\e[33m'; c_cyn=$'\e[36m'; c_0=$'\e[0m'
say()  { printf '%s\n' "$*"; }
ok()   { printf '%s✓%s %s\n' "$c_grn" "$c_0" "$*"; }
warn() { printf '%s!%s %s\n' "$c_yel" "$c_0" "$*"; }
die()  { printf '%s✗ %s%s\n' "$c_red" "$*" "$c_0" >&2; exit 1; }
hdr()  { printf '\n%s== %s ==%s\n' "$c_cyn" "$*" "$c_0"; }

# ---- find esptool (pip 'esptool.py' or IDF's 'esptool') -------------
ESPTOOL=""
find_esptool() {
  for c in esptool.py esptool "python3 -m esptool"; do
    if $c version >/dev/null 2>&1; then ESPTOOL="$c"; return 0; fi
  done
  return 1
}

# ---- locate the serial port ----------------------------------------
find_port() {
  [ -n "${PORT:-}" ] && { echo "$PORT"; return 0; }
  local p
  for p in /dev/ttyACM* /dev/ttyUSB*; do
    [ -e "$p" ] && { echo "$p"; return 0; }
  done
  return 1
}

# ---- permissions hint ----------------------------------------------
check_dialout() {
  local p="$1"
  if [ -e "$p" ] && [ ! -r "$p" ]; then
    warn "No read access to $p. Add yourself to the 'dialout' group:"
    say  "    sudo usermod -aG dialout \$USER   # then log out/in (or: newgrp dialout)"
  fi
}

# =====================================================================
cmd_doctor() {
  hdr "host toolchain"
  if find_esptool; then ok "esptool: $($ESPTOOL version 2>/dev/null | head -1)"
  else warn "esptool not found.  Install (lightweight, needed for detect/flash):"
       say  "    python3 -m pip install --user esptool"; fi

  if command -v idf.py >/dev/null 2>&1; then ok "ESP-IDF: $(idf.py --version 2>/dev/null)"
  else warn "ESP-IDF not found (needed only for build). One-time install (~2GB):"
       say  "    git clone -b v5.3 --recursive https://github.com/espressif/esp-idf.git ~/esp-idf"
       say  "    ~/esp-idf/install.sh esp32,esp32s3,esp32c3"
       say  "    . ~/esp-idf/export.sh        # run this in each new shell before build"; fi

  local p; if p=$(find_port); then ok "serial port: $p"; check_dialout "$p"
  else warn "no /dev/ttyACM* or /dev/ttyUSB* — plug the board in (try a DATA usb cable)."; fi
}

# =====================================================================
cmd_detect() {
  find_esptool || die "esptool missing — run: python3 -m pip install --user esptool"
  local port; port=$(find_port) || die "no serial port. Plug board in; ensure a DATA (not charge-only) cable."
  check_dialout "$port"

  hdr "detecting board on $port"
  local out
  # --no-stub: read chip/flash via ROM loader only. Avoids needing the flasher
  # stub, which the Debian/Ubuntu apt esptool package ships broken (missing
  # stub_flasher_*.json). Flashing later uses ESP-IDF's own (working) esptool.
  if ! out=$($ESPTOOL --port "$port" --before default_reset --no-stub flash_id 2>&1); then
    say "$out"; die "esptool could not talk to the board on $port.
  - Hold BOOT, tap RESET, release BOOT, retry (puts it in download mode).
  - Or set the port explicitly:  PORT=/dev/ttyUSB0 ./atome.sh detect"
  fi
  say "$out"

  # parse
  local chip flash mac target psram="unknown"
  chip=$(sed -n 's/^Chip is \(.*\)/\1/p'        <<<"$out" | head -1)
  flash=$(sed -n 's/.*Detected flash size: \([0-9A-Za-z]*\).*/\1/p' <<<"$out" | head -1)
  mac=$(sed -n 's/^MAC: \(.*\)/\1/p'            <<<"$out" | head -1)

  case "$chip" in
    *ESP32-S3*) target=esp32s3 ;;
    *ESP32-S2*) target=esp32s2 ;;
    *ESP32-C3*) target=esp32c3 ;;
    *ESP32-C6*) target=esp32c6 ;;
    *ESP32*)    target=esp32   ;;
    *)          target=esp32s3 ;;
  esac
  # esptool sometimes reports embedded PSRAM in the Features line
  grep -qiE 'PSRAM|SPIRAM' <<<"$out" && psram="maybe (esptool hint)"

  hdr "summary"
  ok "chip       : ${chip:-?}"
  ok "idf target : $target"
  ok "flash      : ${flash:-?}"
  ok "MAC        : ${mac:-?}"
  ok "PSRAM      : $psram   (definitively confirmed by the boot log after flashing)"

  if { echo "PORT=$port"; echo "TARGET=$target"; echo "FLASH=${flash:-4MB}"; } > "$STATE" 2>/dev/null; then
    say ""; say "Saved to .atome_state. Next:  ./atome.sh analyze"
  else
    warn "couldn't write $STATE (folder is read-only). Fix ownership, or pass settings inline:"
    say  "    sudo chown -R \$USER:\$USER ."
    say  "    TARGET=$target PORT=$port ./atome.sh build   # works without the cache file"
  fi
}

# =====================================================================
cmd_analyze() {
  [ -f "$STATE" ] || { warn "run ./atome.sh detect first"; cmd_detect; }
  # shellcheck disable=SC1090
  source "$STATE"
  hdr "analysis for $TARGET"

  say "Three build profiles (engine is compile-time-sized, so one binary = one model):"
  printf "  %-7s %-26s %-12s %s\n" PROFILE OUTPUT "RAM(state)" REQUIRES
  printf "  %-7s %-26s %-12s %s\n" "full"  "coherent, full context"  "~811 KB" "PSRAM"
  printf "  %-7s %-26s %-12s %s\n" "wroom" "coherent, short context" "~209 KB" "any ESP32 (internal SRAM)"
  printf "  %-7s %-26s %-12s %s\n" "toy"   "gibberish (just a demo)" "~103 KB" "any ESP32"
  say ""
  case "$TARGET" in
    esp32s3) RECO=full
      ok "Recommended: 'full' (944K, PSRAM) — most S3 AI devkits (…R8) have PSRAM."
      say  "  -> ./atome.sh build full  && ./atome.sh flash && ./atome.sh monitor"
      say  "  If boot log says 'PSRAM: NONE':  ./atome.sh build wroom" ;;
    esp32) RECO=wroom
      ok "Recommended: 'wroom' (944K weights, seq=32, internal SRAM) — coherent SHORT output, no PSRAM needed."
      warn "Classic ESP32/WROOM has no PSRAM, so 'full' (811KB) won't fit; 'wroom' (209KB) does."
      say  "  -> ./atome.sh build wroom  && ./atome.sh flash && ./atome.sh monitor"
      say  "  (If you actually have a WROVER w/ PSRAM, use 'full' instead.)" ;;
    esp32c3|esp32s2|esp32c6) RECO=wroom
      warn "$TARGET has no PSRAM; use 'wroom' (944K seq=32, internal SRAM)."
      say  "  -> ./atome.sh build wroom  && ./atome.sh flash && ./atome.sh monitor" ;;
    *) RECO=wroom; warn "unknown target; defaulting to 'wroom'." ;;
  esac
  echo "RECO=$RECO" >> "$STATE" 2>/dev/null || true
}

# =====================================================================
load_state() { [ -f "$STATE" ] && { source "$STATE"; } || true; }

cmd_build() {
  command -v idf.py >/dev/null 2>&1 || die "ESP-IDF not in PATH. Run '. ~/esp-idf/export.sh' first (see ./atome.sh doctor)."
  load_state
  # profile: full | wroom | toy  (arg wins; else RECO; else full). --toy alias kept.
  local profile="${1:-}"
  [ "$profile" = "--toy" ] && profile="toy"
  [ -z "$profile" ] && profile="${RECO:-full}"
  case "$profile" in full|wroom|toy) ;; *) die "unknown profile '$profile' (use: full | wroom | toy)";; esac
  local target="${TARGET:-esp32s3}"

  # weights blob + sdkconfig overlay per profile
  local sdk="sdkconfig.defaults" blob model_desc
  case "$profile" in
    toy)   blob=model_toy.atome;  model_desc="toy 20KB (gibberish, fits anything)";;
    wroom) blob=model_full.atome; model_desc="944K seq=32 internal-SRAM (short coherent)"; sdk="sdkconfig.defaults;sdkconfig.wroom";;
    full)  blob=model_full.atome; model_desc="944K seq=128 PSRAM (full coherent)";          sdk="sdkconfig.defaults;sdkconfig.psram";;
  esac

  hdr "build  (target=$target, profile=$profile)"
  ok "model: $model_desc"
  cp "$MAIN/$blob" "$MAIN/model.atome"

  ( cd "$FW"
    rm -f sdkconfig
    idf.py -D SDKCONFIG_DEFAULTS="$sdk" set-target "$target"
    idf.py -D SDKCONFIG_DEFAULTS="$sdk" -D ATOME_PROFILE="$profile" build )
  ok "build done. Next:  ./atome.sh flash"
}

cmd_flash() {
  load_state
  local port; port="${PORT:-$(find_port)}" || die "no serial port found."
  local target="${TARGET:-esp32}"
  hdr "flashing on $port"

  # Preferred path: ESP-IDF present -> let it flash.
  if command -v idf.py >/dev/null 2>&1; then
    ( cd "$FW" && idf.py -p "$port" flash )
    ok "flashed. Watch it run:  ./atome.sh monitor"; return 0
  fi

  # Fallback: no IDF, but we have the built binaries — flash with plain esptool.
  local b="$FW/build"
  local boot="$b/bootloader/bootloader.bin"
  local part="$b/partition_table/partition-table.bin"
  local app; app=$(ls "$b"/*.bin 2>/dev/null | grep -vE 'bootloader|partition' | head -1)
  [ -f "$boot" ] && [ -f "$part" ] && [ -n "$app" ] || \
    die "no built firmware in $b — build it first (I build it for you): ./atome.sh build wroom"
  find_esptool || die "need esptool:  python3 -m pip install --user --break-system-packages esptool"

  # esp32 default offsets: bootloader 0x1000, partition-table 0x8000, app 0x10000.
  # --no-stub dodges the broken Debian/Ubuntu apt esptool stub data file.
  say "using esptool (no IDF). app: $(basename "$app")"
  $ESPTOOL --chip "$target" --port "$port" --baud "${ESPTOOL_BAUD:-460800}" \
    --before default_reset --after hard_reset --no-stub \
    write_flash -z \
    0x1000  "$boot" \
    0x8000  "$part" \
    0x10000 "$app" \
    || die "esptool flash failed. Try a lower baud:  PORT=$port ESPTOOL_BAUD=115200 ./atome.sh flash
  Or hold BOOT, tap RESET, release BOOT, then re-run."
  ok "flashed. Watch it run:  ./atome.sh monitor"
}

cmd_monitor() {
  load_state
  local port; port="${PORT:-$(find_port)}" || die "no serial port found."
  hdr "monitor on $port  (Ctrl-] to exit)"
  if command -v idf.py >/dev/null 2>&1; then ( cd "$FW" && idf.py -p "$port" monitor )
  else warn "ESP-IDF not present; falling back to a raw serial view."
       command -v python3 >/dev/null && python3 -m serial.tools.miniterm "$port" 115200 || \
       die "install pyserial:  python3 -m pip install --user pyserial"; fi
}

cmd_all() {
  cmd_doctor; cmd_detect; cmd_analyze; cmd_build; cmd_flash; cmd_monitor
}

cmd_clean() { rm -rf "$FW/build" "$STATE"; ok "cleaned."; }

# =====================================================================
case "${1:-}" in
  detect)  cmd_detect ;;
  analyze) cmd_analyze ;;
  doctor)  cmd_doctor ;;
  build)   shift; cmd_build "${1:-}" ;;
  flash)   cmd_flash ;;
  monitor) cmd_monitor ;;
  all)     cmd_all ;;
  clean)   cmd_clean ;;
  ""|-h|--help)
    awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' "${BASH_SOURCE[0]}" ;;
  *) die "unknown command '$1' (try: detect | analyze | doctor | build | flash | monitor | all)" ;;
esac

"""superesp.esp32.capture — read the board's serial battery report to a file.

Primary path: pyserial (toggles DTR/RTS to reset the board, then reads).
Fallback (no pyserial): stty + read the tty directly, kicking a reset via esptool
if present (otherwise: press the board's EN/RESET button when prompted).
Reads until "BATTERY DONE" or timeout, saves the raw log.

Usage:  python3 -m superesp.esp32.capture <port> [out.log] [timeout_s]
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path


def _via_pyserial(port, out: Path, timeout_s: float) -> bool:
    try:
        import serial
    except ImportError:
        return False
    ser = serial.Serial(port, 115200, timeout=1)
    try:
        ser.dtr = False; ser.rts = True; time.sleep(0.1)
        ser.rts = False; time.sleep(0.1)   # pulse reset so we catch the boot battery
    except Exception:
        pass
    buf, t0 = [], time.time()
    while time.time() - t0 < timeout_s:
        line = ser.readline().decode(errors="replace")
        if line:
            sys.stdout.write(line); sys.stdout.flush(); buf.append(line)
            if "BATTERY DONE" in line:
                break
    ser.close()
    out.write_text("".join(buf))
    return True


def _via_stty(port, out: Path, timeout_s: float) -> bool:
    if not shutil.which("stty"):
        return False
    # raw mode, per-read timeout 2.0s (min 0 time 20 = tenths of a second)
    subprocess.run(["stty", "-F", port, "115200", "raw", "-echo", "min", "0", "time", "20"],
                   check=False)
    # kick a reset so the board reboots and prints the battery, if esptool exists
    et = None
    for c in (["esptool.py"], ["esptool"], [sys.executable, "-m", "esptool"]):
        if shutil.which(c[0]) or c[0] == sys.executable:
            et = c; break
    if et:
        subprocess.Popen(et + ["--port", port, "--before", "default_reset",
                               "--after", "hard_reset", "--no-stub", "flash_id"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print("[capture] no pyserial/esptool to reset — press the board's EN/RESET button now.")
    buf, t0 = [], time.time()
    with open(port, "rb", buffering=0) as f:
        while time.time() - t0 < timeout_s:
            chunk = f.readline()
            if chunk:
                s = chunk.decode(errors="replace")
                sys.stdout.write(s); sys.stdout.flush(); buf.append(s)
                if "BATTERY DONE" in s:
                    break
    out.write_text("".join(buf))
    return True


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: capture.py <port> [out.log] [timeout_s]")
    port = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("battery_serial.log")
    timeout_s = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
    # if the chosen log path isn't writable (e.g. dir owned by another user),
    # fall back to a temp file instead of crashing the whole run.
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        test = out.parent / ".w"; test.write_text(""); test.unlink()
    except Exception:
        import tempfile
        out = Path(tempfile.gettempdir()) / out.name
        print(f"[capture] reports dir not writable; using {out}")
    ok = _via_pyserial(port, out, timeout_s) or _via_stty(port, out, timeout_s)
    if not ok:
        raise SystemExit("no capture method (need pyserial OR stty). "
                         "Run manually:  idf.py -p %s monitor" % port)
    n = len(out.read_text(errors="replace").splitlines()) if out.exists() else 0
    print(f"\n[capture] saved {n} lines -> {out}")


if __name__ == "__main__":
    main()

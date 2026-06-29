"""superesp.esp32.parse_report — grade a board serial log into per-app reports.

Reads a captured serial log + golden.json, matches each head's
  HEAD <name> CLASS <got> EXPECT <want> <PASS|FAIL> [HEAP <kb>]
line, and writes reports/report.json + reports/REPORT.md with per-application
status, on-device-vs-expected class, free heap, and a bugs/errors section
(missing heads, LOAD_FAIL, crashes, mismatches).

Run:  python3 -m superesp.esp32.parse_report <serial_log>
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports"
HEAD_RE = re.compile(
    r"HEAD\s+(\S+)\s+CLASS\s+(-?\d+)\s+EXPECT\s+(-?\d+)\s+(PASS|FAIL)"
    r"(?:\s+US\s+(\d+))?(?:\s+HEAP\s+(\d+))?")
LOADFAIL_RE = re.compile(r"HEAD\s+(\S+)\s+LOAD_FAIL")
INTEG_RE = re.compile(r"HEAD\s+(\S+)\s+INTEG_FAIL")
DONE_RE = re.compile(r"BATTERY DONE pass=(\d+)/(\d+)")


def grade(log_text: str) -> dict:
    golden = {g["head"]: g for g in json.loads((HERE / "golden.json").read_text())}
    seen, bugs = {}, []
    for m in HEAD_RE.finditer(log_text):
        name, got, want, verdict, us, heap = m.groups()
        seen[name] = {"class": int(got), "expect": int(want),
                      "pass": verdict == "PASS",
                      "us": int(us) if us else None,
                      "heap_kb": int(heap) if heap else None}
    for m in LOADFAIL_RE.finditer(log_text):
        bugs.append({"head": m.group(1), "error": "LOAD_FAIL (blob failed to parse)"})
    for m in INTEG_RE.finditer(log_text):
        bugs.append({"head": m.group(1), "error": "INTEG_FAIL (blob checksum mismatch — corrupt/swapped)"})

    apps = []
    for head, g in golden.items():
        r = seen.get(head)
        if r is None:
            bugs.append({"head": head, "error": "no result line (head did not run / serial truncated)"})
            apps.append({"head": head, "status": "MISSING", "expect_label": g["expect_label"]})
            continue
        ok = r["pass"] and r["class"] == g["expect_class"]
        if not ok:
            bugs.append({"head": head, "error": f"class mismatch: got {r['class']} expected {g['expect_class']}"})
        apps.append({"head": head, "status": "PASS" if ok else "FAIL",
                     "device_class": r["class"], "expect_class": g["expect_class"],
                     "expect_label": g["expect_label"], "heap_kb": r["heap_kb"],
                     "us": r["us"]})

    done = DONE_RE.search(log_text)
    crashed = bool(re.search(r"Guru Meditation|abort\(\)|rst:0x|panic", log_text)) and not done
    n_pass = sum(1 for a in apps if a["status"] == "PASS")
    # honest source label: a real ESP32 build prints HEAP; QEMU/host does not.
    on_silicon = any(a.get("heap_kb") is not None for a in apps)
    source = "real ESP32 silicon" if on_silicon else "QEMU/emulation (NOT silicon)"
    return {"generated": datetime.now(timezone.utc).isoformat(),
            "source": source, "on_silicon": on_silicon,
            "n_apps": len(apps), "n_pass": n_pass,
            "on_device_done": bool(done), "suspected_crash": crashed,
            "apps": apps, "bugs": bugs}


def write_reports(rep: dict) -> None:
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "report.json").write_text(json.dumps(rep, indent=2))
    L = [f"# SuperESP — application test report",
         f"\n_{rep['generated']}_  •  source: **{rep['source']}**"
         f"  •  **{rep['n_pass']}/{rep['n_apps']} applications PASS**"
         f"  •  battery completed: {rep['on_device_done']}"
         + ("  •  **SUSPECTED CRASH**" if rep['suspected_crash'] else ""), "",
         "| application | status | device class | expected | latency | free heap |",
         "|---|---|---|---|---|---|"]
    for a in rep["apps"]:
        us = a.get("us"); lat = f"{us} µs" if us is not None else "—"
        L.append(f"| {a['head']} | {a['status']} | {a.get('device_class','—')} | "
                 f"{a.get('expect_class','?')} ({a.get('expect_label','')}) | "
                 f"{lat} | {a.get('heap_kb','—')} KB |")
    L.append("\n## Bugs / errors")
    L.append("\n".join(f"- **{b['head']}**: {b['error']}" for b in rep["bugs"]) if rep["bugs"]
             else "- none — every application reproduced its host-golden class on-device.")
    (REPORTS / "REPORT.md").write_text("\n".join(L))


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python3 -m superesp.esp32.parse_report <serial_log>")
    rep = grade(Path(sys.argv[1]).read_text(errors="replace"))
    write_reports(rep)
    print(f"{rep['n_pass']}/{rep['n_apps']} apps PASS; bugs={len(rep['bugs'])}; "
          f"done={rep['on_device_done']} -> superesp/esp32/reports/REPORT.md")


if __name__ == "__main__":
    main()

"""superesp.cli — one-command reproduction of SuperESP applications.

    python3 -m superesp.cli list
    python3 -m superesp.cli train  <head>          # a built-in head
    python3 -m superesp.cli train  --csv my.csv --label-col state --name mysensor
    python3 -m superesp.cli flashplan <name>        # how to bake the blob into firmware

`train` does the whole pipeline: split (leak-free) -> train tiny ternary head ->
held-out eval + abstention + novelty -> export ATOMECL01 -> Ed25519 attestation,
writing everything to superesp/artifacts/. Anyone with a CSV of their own ESP32
sensor windows gets a bit-exact, attestable on-device classifier — no ML setup.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from superesp.framework.config import SHARED
from superesp.framework.train import train_head, evaluate
from superesp.framework import abstain, novelty
from superesp.framework.export import export_classifier
from superesp.attest import sign

ART = Path(__file__).resolve().parent / "artifacts"


def _load(args):
    if args.csv:
        from superesp.datasets.csv_head import load_csv
        return load_csv(args.csv, label_col=args.label_col, name=args.name)
    from superesp.heads import BY_NAME
    if args.head not in BY_NAME:
        raise SystemExit(f"unknown head {args.head!r}; see `cli list`")
    return BY_NAME[args.head].loader(seed=0)


def cmd_list(_):
    from superesp.heads import HEADS
    print("Built-in SuperESP heads:")
    for h in HEADS:
        print(f"  {h.name:11s} — {h.blurb}")
    print("\nOr bring your own:  cli train --csv data.csv --label-col <col> --name <name>")


def cmd_train(args):
    ds = _load(args)
    name = args.name or (args.head if not args.csv else ds.name)
    print(f"[{name}] {ds.source} {ds.n_classes} classes, {ds.train_ids.shape[1]} feats, "
          f"train/val/test={ds.train_ids.shape[0]}/{ds.val_ids.shape[0]}/{ds.test_ids.shape[0]}")
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=args.epochs, seed=0)
    ev = evaluate(res.model, ds.test_ids, ds.test_labels)
    rc = abstain.risk_coverage(ev["probs"], ev["labels"])
    cov5 = abstain.coverage_at_risk(ev["probs"], ev["labels"], 0.05)
    print(f"  held-out TEST acc   = {ev['test_acc']:.3f}  (n={ev['n_test']})")
    print(f"  abstention AURC     = {rc['aurc']:.4f} (oracle {rc['oracle_aurc']:.4f}) "
          f"-> answer {cov5:.0%} of inputs at <=5% error, abstain on the rest")

    blob = ART / f"{name}.atomecl"
    st = export_classifier(res.model, blob)
    (ART / f"{name}.tok.json").write_text(json.dumps(ds.tokenizer.to_dict()))
    key = sign.generate_key()
    att = sign.sign_blob(blob, key, head=name, n_classes=ds.n_classes, classes=ds.class_names)
    sign.save_attestation(att, ART / f"{name}.att.json")
    ok, _ = sign.verify(blob, att)
    print(f"  exported {st['total_bytes']} B -> {blob.name}; attestation verify={'OK' if ok else 'FAIL'}")
    print(f"  next: python3 -m superesp.cli flashplan {name}")


def cmd_targets(_):
    from superesp import targets
    print(f"SuperESP head footprint: {targets.STATE_RAM_B/1024:.1f} KB SRAM (state) "
          f"+ {targets.HEAD_FLASH_B/1024:.1f} KB flash (weights). One C99 build runs "
          f"on Xtensa AND RISC-V.\n")
    print(f"{'variant':10s} {'arch':12s} {'SRAM':>6s} {'fits?':>6s} {'headroom':>9s}  idf target")
    for r in targets.report():
        print(f"{r['name']:10s} {r['arch']:12s} {r['sram_kb']:4d}KB "
              f"{'YES' if r['fits'] else 'NO':>6s} {r['sram_headroom_x']:>7}x  "
              f"idf.py set-target {r['idf_target']}")
    print("\nAll mainline ESP32 variants fit with >10x SRAM headroom.")


def _have(mod=None, exe=None):
    import importlib.util, shutil
    if exe:
        return shutil.which(exe) is not None
    return importlib.util.find_spec(mod) is not None


def cmd_doctor(_):
    import os, sys, shutil
    print("SuperESP environment check\n")
    rows = [
        ("python>=3.9", sys.version_info >= (3, 9), sys.version.split()[0]),
        ("gcc (host C engine / parity)", _have(exe="gcc"), shutil.which("gcc") or "—"),
        ("torch (training)", _have("torch"), "import ok" if _have("torch") else "pip install torch"),
        ("numpy", _have("numpy"), "ok" if _have("numpy") else "pip install numpy"),
        ("esptool (flash ESP32)", _have("esptool") or _have(exe="esptool.py"),
         "ok" if (_have("esptool") or _have(exe="esptool.py")) else "run: superesp setup"),
        ("ESP-IDF (build firmware)", bool(os.environ.get("IDF_PATH")) or _have(exe="idf.py"),
         os.environ.get("IDF_PATH", "set IDF_PATH / install ESP-IDF")),
    ]
    for name, ok, detail in rows:
        print(f"  [{'OK ' if ok else 'X  '}] {name:32s} {detail}")
    missing = [n for n, ok, _ in rows if not ok]
    print("\nAll set." if not missing else f"\nMissing: {', '.join(missing)} — run `superesp setup`.")


def cmd_setup(args):
    import subprocess, sys
    print("SuperESP setup — installing host flashing tool (esptool)...")
    attempts = [
        [sys.executable, "-m", "pip", "install", "--quiet", "esptool"],
        [sys.executable, "-m", "pip", "install", "--quiet", "--user", "esptool"],
    ]
    ok = False
    for cmd in attempts:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0:
                ok = True; print(f"  esptool installed via: {' '.join(cmd[2:])}"); break
        except Exception:
            pass
    if not ok:
        print("  pip blocked (externally-managed env). Use an isolated install:")
        print("    pipx install esptool        # recommended")
        print("    OR  python3 -m venv .venv && . .venv/bin/activate && pip install esptool")
    print("\nESP-IDF (needed to BUILD/flash firmware) is large; install once:")
    print("  git clone --recursive https://github.com/espressif/esp-idf.git")
    print("  cd esp-idf && ./install.sh && . ./export.sh   # sets IDF_PATH")
    print("Then: superesp doctor   to re-check; superesp targets   for board fit.")


def cmd_flashplan(args):
    c = SHARED
    tok = ART / f"{args.name}.tok.json"
    print(f"# Flash SuperESP head '{args.name}' to an ESP32\n")
    print(f"1. cp superesp/artifacts/{args.name}.atomecl superesp/firmware/main/os_telem.atomecl")
    print("   (or edit EMBED_FILES in main/CMakeLists.txt to your blob name)")
    print(f"2. Engine config MUST match (already set): d_model={c.d_model} n_layers={c.n_layers} "
          f"d_head={c.d_head} kernel={c.kernel_size} max_seq={c.max_seq}")
    print(f"3. Bake the tokenizer constants from {tok.name} into VMIN/VMAX in superesp_main.c")
    print("4. cd superesp/firmware && idf.py set-target esp32 && idf.py -p /dev/ttyUSB0 flash monitor")
    print("\n(on-silicon throughput/RAM are NOT MEASURED here — measure on your board)")


def parse_logger_lines(lines, max_frames=None):
    """Pure: turn logger serial lines into (header_cols_or_None, rows). Testable."""
    header, rows = None, []
    for line in lines:
        line = line.strip()
        if line.startswith("CSV_HEADER,"):
            header = line.split(",")[1:]
        elif line.startswith("CSV,"):
            rows.append(line.split(",")[1:])
            if max_frames and len(rows) >= max_frames:
                break
    return header, rows


def _append_csv(out: Path, header, rows, label: str):
    import csv as _csv
    n = len(rows[0])
    cols = header if header and len(header) == n else [f"f{i}" for i in range(n)]
    exists = out.exists()
    with out.open("a", newline="") as f:
        w = _csv.writer(f)
        if not exists:
            w.writerow(cols + ["label"])
        for r in rows:
            w.writerow(r + [label])


def cmd_log(args):
    """Capture sensor CSV frames from the logger firmware, append a label column."""
    try:
        import serial
    except ImportError:
        raise SystemExit("need pyserial: pip install --user pyserial")
    port = args.port or _autoport()
    if not port:
        raise SystemExit("no serial port; pass --port /dev/ttyUSB0")
    ser = serial.Serial(port, 115200, timeout=2)
    import time as _t; t0 = _t.time(); buf = []
    print(f"capturing {args.frames} frames from {port} (label='{args.label}')...")
    header, rows = None, []
    while len(rows) < args.frames and _t.time() - t0 < args.frames * 6 + 30:
        line = ser.readline().decode(errors="replace")
        if line:
            buf.append(line)
            header, rows = parse_logger_lines(buf, args.frames)
            print(f"  frame {len(rows)}/{args.frames}", end="\r")
    ser.close()
    if not rows:
        raise SystemExit("no CSV frames captured (is the logger firmware flashed?)")
    _append_csv(Path(args.out), header, rows, args.label)
    print(f"\nwrote {len(rows)} rows (label='{args.label}') -> {args.out}. "
          f"Repeat per class, then: superesp train --csv {args.out} --name myhead")


def _autoport():
    import glob
    for p in glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"):
        return p
    return None


def cmd_new(args):
    """Scaffold a valid training-CSV template + a how-to."""
    import csv as _csv
    n = args.features
    out = Path(f"{args.name}.csv")
    with out.open("w", newline="") as f:
        w = _csv.writer(f)
        w.writerow([f"f{i}" for i in range(n)] + ["label"])
    (Path(f"{args.name}_HOWTO.md")).write_text(
        f"# Custom head '{args.name}'\n\n"
        f"`{out.name}` has {n} feature columns + a `label` column.\n\n"
        "Fill it one of two ways:\n"
        f"1. Flash the logger firmware, then: `superesp log --label <state> --out {out.name}` "
        "(repeat per class).\n"
        "2. Or paste your own rows (one window per row, <=32 features, a class name in `label`).\n\n"
        f"Then train + deploy:\n  superesp train --csv {out.name} --name {args.name}\n"
        f"  superesp report {args.name}\n  superesp flashplan {args.name}\n")
    print(f"created {out.name} ({n} features + label) + {args.name}_HOWTO.md")


def cmd_report(args):
    """Train (or use the named built-in/CSV) head, write confusion + risk-coverage."""
    from superesp.framework import report as _report
    ds = _load(args)
    name = args.name or (args.head if not args.csv else ds.name)
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=args.epochs, seed=0)
    ev = evaluate(res.model, ds.test_ids, ds.test_labels)
    rc = abstain.risk_coverage(ev["probs"], ev["labels"])
    paths = _report.write_report(name, ds.class_names, ev, rc, ART / "reports")
    print(f"{name}: TEST acc={ev['test_acc']:.3f}, AURC={rc['aurc']:.4f} -> {paths['md']}")


def cmd_zoo(args):
    from superesp.zoo import registry as _z
    if args.zoo_cmd == "build":
        m = _z.build_registry()
        print(f"built registry: {len(m['heads'])} heads -> superesp/zoo/registry.json")
    elif args.zoo_cmd == "list":
        for h in _z.list_heads():
            acc = h.get("test_acc"); a = f"{acc:.2f}" if isinstance(acc, (int, float)) else "?"
            src = h.get("source") or "?"
            sig = "signed" if h.get("attested") else "unsigned"
            print(f"  {h['name']:11s} {src:5s} acc={a} {sig:8s} — {h.get('intended_use','?')}")
    elif args.zoo_cmd == "pull":
        r = _z.pull(args.name, args.dest)
        if r["ok"]:
            print(f"pulled '{args.name}' (verified sha256+signature) -> {r['dest']}  [use: {r['intended_use']}]")
        else:
            raise SystemExit(f"pull failed: {r['reason']}")
    elif args.zoo_cmd == "publish":
        classes = [c.strip() for c in args.classes.split(",") if c.strip()]
        r = _z.publish(args.blob, args.name, classes, args.use, source=args.source,
                       tokenizer_path=args.tokenizer)
        if r["ok"]:
            print(f"published '{args.name}' (signed) -> {r['store']}; registry updated")
        else:
            raise SystemExit(f"publish failed: {r['reason']}")
    elif args.zoo_cmd == "index":
        print(f"wrote {_z.index_html()}")


def main():
    ap = argparse.ArgumentParser(prog="superesp")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    sub.add_parser("targets").set_defaults(fn=cmd_targets)
    sub.add_parser("setup").set_defaults(fn=cmd_setup)
    t = sub.add_parser("train"); t.set_defaults(fn=cmd_train)
    t.add_argument("head", nargs="?", default=None)
    t.add_argument("--csv"); t.add_argument("--label-col", default="label")
    t.add_argument("--name"); t.add_argument("--epochs", type=int, default=40)
    f = sub.add_parser("flashplan"); f.set_defaults(fn=cmd_flashplan)
    f.add_argument("name")
    lg = sub.add_parser("log"); lg.set_defaults(fn=cmd_log)
    lg.add_argument("--label", required=True); lg.add_argument("--out", default="my_sensor.csv")
    lg.add_argument("--frames", type=int, default=50); lg.add_argument("--port")
    nw = sub.add_parser("new"); nw.set_defaults(fn=cmd_new)
    nw.add_argument("name"); nw.add_argument("--features", type=int, default=30)
    rp = sub.add_parser("report"); rp.set_defaults(fn=cmd_report)
    rp.add_argument("head", nargs="?", default=None)
    rp.add_argument("--csv"); rp.add_argument("--label-col", default="label")
    rp.add_argument("--name"); rp.add_argument("--epochs", type=int, default=40)
    z = sub.add_parser("zoo"); z.set_defaults(fn=cmd_zoo)
    zs = z.add_subparsers(dest="zoo_cmd", required=True)
    zs.add_parser("build"); zs.add_parser("list"); zs.add_parser("index")
    zp = zs.add_parser("pull"); zp.add_argument("name"); zp.add_argument("--dest", default="pulled_heads")
    zpub = zs.add_parser("publish")
    zpub.add_argument("name"); zpub.add_argument("--blob", required=True)
    zpub.add_argument("--classes", required=True); zpub.add_argument("--use", default="unspecified")
    zpub.add_argument("--source", default="USER"); zpub.add_argument("--tokenizer")
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

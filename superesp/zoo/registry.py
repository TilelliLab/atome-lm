"""superesp.zoo.registry — build / list / pull signed heads.

build_registry(): scan artifacts/ -> superesp/zoo/registry.json (name, sha256,
  classes, source, test_acc, intended_use, files, attestation).
list_heads(): read the manifest.
pull(name, dest): copy blob+tokenizer(+attestation) to dest, VERIFY sha256 +
  Ed25519 signature; refuse to install on mismatch.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from superesp.attest import sign

HERE = Path(__file__).resolve().parent
ART = HERE.parent / "artifacts"
STORE = HERE / "store"            # published (community) heads live here
MANIFEST = HERE / "registry.json"
INDEX = HERE / "index.html"

# generic intended-use per head (ties into the saved guardrails plan)
INTENDED = {
    "agri": "agricultural soil/climate monitoring",
    "voice": "on-device farm voice commands",
    "motion": "activity/gesture/fall detection",
    "sound_scene": "ambient acoustic-event detection",
    "anomaly": "machine predictive maintenance",
    "air": "air-quality / gas-leak safety",
    "os_telem": "device health supervision",
    "power": "energy / NILM load monitoring",
    "occupancy": "room occupancy (HVAC/lighting)",
    "wearable": "fitness activity (NOT a medical device)",
    "water": "leak/flood safety",
    "forecast": "predictive time-to-failure",
}


def _sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _entry_from(blob: Path, rows: dict, src_dir_rel: str, att: Path) -> dict:
    name = blob.stem
    r = rows.get(name, {})
    return {
        "name": name, "sha256": _sha256(blob), "blob_bytes": blob.stat().st_size,
        "classes": r.get("classes", []), "n_classes": r.get("n_classes"),
        "source": r.get("source"), "test_acc": r.get("test_acc"),
        "intended_use": r.get("intended_use") or INTENDED.get(name, "unspecified"),
        "files": {"blob": f"{src_dir_rel}/{name}.atomecl",
                  "tokenizer": f"{src_dir_rel}/{name}.tok.json",
                  "attestation": f"{src_dir_rel}/{name}.att.json" if att.exists() else None},
        "attested": att.exists(),
    }


def build_registry() -> dict:
    rows = {r["head"]: r for r in json.loads((ART / "RESULTS.json").read_text())}
    entries = []
    seen = set()
    # built-in heads (artifacts/) + published heads (store/)
    for blob in sorted(ART.glob("*.atomecl")):
        entries.append(_entry_from(blob, rows, "artifacts", ART / f"{blob.stem}.att.json"))
        seen.add(blob.stem)
    if STORE.exists():
        for blob in sorted(STORE.glob("*.atomecl")):
            if blob.stem in seen:
                continue
            cardp = STORE / f"{blob.stem}.card.json"
            card = json.loads(cardp.read_text()) if cardp.exists() else {}
            rows[blob.stem] = card
            entries.append(_entry_from(blob, rows, "zoo/store", STORE / f"{blob.stem}.att.json"))
    manifest = {"registry": "superesp-local", "version": 1, "heads": entries}
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    return manifest


def list_heads() -> list:
    if not MANIFEST.exists():
        build_registry()
    return json.loads(MANIFEST.read_text())["heads"]


def pull(name: str, dest, verify: bool = True) -> dict:
    dest = Path(dest); dest.mkdir(parents=True, exist_ok=True)
    heads = {h["name"]: h for h in list_heads()}
    if name not in heads:
        return {"ok": False, "reason": f"unknown head '{name}'"}
    h = heads[name]
    src_blob = HERE.parent / h["files"]["blob"]
    if not src_blob.exists():
        return {"ok": False, "reason": f"blob missing: {src_blob}"}
    if verify:
        if _sha256(src_blob) != h["sha256"]:
            return {"ok": False, "reason": "sha256 mismatch (registry vs blob)"}
        att_rel = h["files"].get("attestation")
        if att_rel:
            att = json.loads((HERE.parent / att_rel).read_text())
            ok, why = sign.verify(src_blob, att)
            if not ok:
                return {"ok": False, "reason": f"attestation failed: {why}"}
    # install (verified)
    for key in ("blob", "tokenizer", "attestation"):
        rel = h["files"].get(key)
        if rel and (HERE.parent / rel).exists():
            shutil.copy2(HERE.parent / rel, dest / Path(rel).name)
    return {"ok": True, "name": name, "verified": verify, "dest": str(dest),
            "intended_use": h["intended_use"]}


def publish(blob_path, name, classes, intended_use, source="USER",
            test_acc=None, tokenizer_path=None) -> dict:
    """Add a head to the zoo store: copy blob, sign it, write a model card, rebuild."""
    blob_path = Path(blob_path)
    if not blob_path.exists():
        return {"ok": False, "reason": f"blob not found: {blob_path}"}
    STORE.mkdir(parents=True, exist_ok=True)
    dst = STORE / f"{name}.atomecl"
    shutil.copy2(blob_path, dst)
    if tokenizer_path and Path(tokenizer_path).exists():
        shutil.copy2(tokenizer_path, STORE / f"{name}.tok.json")
    key = sign.generate_key()
    att = sign.sign_blob(dst, key, head=name, n_classes=len(classes), classes=list(classes))
    sign.save_attestation(att, STORE / f"{name}.att.json")
    card = {"head": name, "classes": list(classes), "n_classes": len(classes),
            "source": source, "test_acc": test_acc, "intended_use": intended_use}
    (STORE / f"{name}.card.json").write_text(json.dumps(card, indent=2))
    build_registry()
    return {"ok": True, "name": name, "store": str(dst)}


def index_html() -> str:
    heads = list_heads()
    rows = ""
    for h in heads:
        acc = h.get("test_acc"); a = f"{acc:.2f}" if isinstance(acc, (int, float)) else "—"
        badge = "✅ signed" if h.get("attested") else "⚠ unsigned"
        rows += (f"<tr><td><b>{h['name']}</b></td><td>{h.get('source') or '?'}</td>"
                 f"<td>{a}</td><td>{h.get('n_classes') or '?'}</td><td>{badge}</td>"
                 f"<td>{h.get('intended_use','')}</td>"
                 f"<td style='font:11px monospace'>{h['sha256'][:16]}…</td></tr>")
    html = f"""<!doctype html><meta charset=utf-8><title>SuperESP model zoo</title>
<body style="font-family:system-ui;max-width:900px;margin:2rem auto">
<h2>SuperESP model zoo — {len(heads)} heads</h2>
<p>Each head is an attested ATOMECL01 blob (sha256 + Ed25519). <code>superesp zoo pull &lt;name&gt;</code>
verifies the signature before installing.</p>
<table border=1 cellpadding=6 style="border-collapse:collapse">
<tr><th>head</th><th>data</th><th>acc</th><th>classes</th><th>signed</th><th>intended use</th><th>sha256</th></tr>
{rows}</table></body>"""
    INDEX.write_text(html)
    return str(INDEX)

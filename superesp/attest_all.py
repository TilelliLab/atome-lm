"""superesp.attest_all — sign every exported head blob + verify the receipts.

Generates one Ed25519 key for the suite, writes <head>.att.json next to each
<head>.atomecl, and verifies all of them (including a deliberate tamper check).
Run after train_all:  python3 -m superesp.attest_all
"""
from __future__ import annotations

import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from superesp.heads import HEADS
from superesp.attest import sign

ART = Path(__file__).resolve().parent / "artifacts"


def run() -> dict:
    key = sign.generate_key()
    # persist the public key for verifiers (private key stays out of the repo)
    pub_hex = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    (ART / "suite_pubkey.txt").write_text(pub_hex + "\n")

    results = []
    for head in HEADS:
        blob = ART / f"{head.name}.atomecl"
        if not blob.exists():
            results.append({"head": head.name, "status": "MISSING_BLOB"})
            continue
        # class names live in RESULTS.json; fall back to count from the blob header
        rj = json.loads((ART / "RESULTS.json").read_text())
        row = next((r for r in rj if r["head"] == head.name), None)
        classes = row["classes"] if row else []
        n_classes = row["n_classes"] if row else 0
        att = sign.sign_blob(blob, key, head=head.name,
                             n_classes=n_classes, classes=classes)
        sign.save_attestation(att, ART / f"{head.name}.att.json")
        ok, reason = sign.verify(blob, att)
        results.append({"head": head.name, "signed": True, "verify_ok": ok,
                        "reason": reason})
        print(f"[{head.name:11s}] signed, verify={'OK' if ok else 'FAIL:'+reason}")
    (ART / "ATTESTATION.json").write_text(json.dumps(results, indent=2))
    return {"pubkey": pub_hex, "heads": results}


if __name__ == "__main__":
    run()

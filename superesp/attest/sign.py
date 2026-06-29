"""superesp.attest.sign — Ed25519 receipts for head binaries.

receipt = {
  "magic": "SESPATT1",
  "head": <name>, "n_classes": int, "classes": [...],
  "sha256": <hex of the ATOMECL01 blob>,
  "blob_bytes": int, "created": <iso8601>,
  "pubkey": <hex>,
}
signature = Ed25519_sign(privkey, canonical_json(receipt))

verify() recomputes sha256(blob), re-serializes the receipt canonically, and
checks the signature against the pubkey IN THE RECEIPT — so tampering with the
blob, the metadata, or the signature is all caught. Verification needs only the
public key (the verifier never holds the secret).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

MAGIC = "SESPATT1"


def generate_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def _pub_hex(priv: Ed25519PrivateKey) -> str:
    raw = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return raw.hex()


def _canonical(receipt: dict) -> bytes:
    return json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()


def sign_blob(blob_path: Path, priv: Ed25519PrivateKey, *,
              head: str, n_classes: int, classes: list[str]) -> dict:
    blob = Path(blob_path).read_bytes()
    receipt = {
        "magic": MAGIC,
        "head": head,
        "n_classes": n_classes,
        "classes": list(classes),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "blob_bytes": len(blob),
        "created": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "pubkey": _pub_hex(priv),
    }
    sig = priv.sign(_canonical(receipt))
    return {"receipt": receipt, "signature": sig.hex()}


def verify(blob_path: Path, attestation: dict) -> tuple[bool, str]:
    """Returns (ok, reason). ok=True only if blob, metadata, and sig all check."""
    receipt = attestation.get("receipt", {})
    sig_hex = attestation.get("signature", "")
    if receipt.get("magic") != MAGIC:
        return False, "bad magic"
    try:
        blob = Path(blob_path).read_bytes()
    except OSError as e:
        return False, f"cannot read blob: {e}"
    if hashlib.sha256(blob).hexdigest() != receipt.get("sha256"):
        return False, "sha256 mismatch (blob tampered or wrong file)"
    if len(blob) != receipt.get("blob_bytes"):
        return False, "blob size mismatch"
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(receipt["pubkey"]))
        pub.verify(bytes.fromhex(sig_hex), _canonical(receipt))
    except (InvalidSignature, ValueError, KeyError) as e:
        return False, f"signature invalid: {e}"
    return True, "ok"


def save_attestation(att: dict, path: Path) -> None:
    Path(path).write_text(json.dumps(att, indent=2))

"""Attestation: a valid receipt verifies; any tamper (blob/metadata/sig) fails."""
import json
import tempfile
from pathlib import Path

from superesp.attest import sign


def _blob(tmp: Path) -> Path:
    p = tmp / "head.atomecl"
    p.write_bytes(b"ATOMECL01" + b"\x05\x00\x00\x00" + bytes(range(256)) * 4)
    return p


def test_sign_and_verify_ok():
    tmp = Path(tempfile.mkdtemp())
    blob = _blob(tmp)
    key = sign.generate_key()
    att = sign.sign_blob(blob, key, head="agri", n_classes=5, classes=list("abcde"))
    ok, reason = sign.verify(blob, att)
    assert ok, reason


def test_tampered_blob_rejected():
    tmp = Path(tempfile.mkdtemp())
    blob = _blob(tmp)
    key = sign.generate_key()
    att = sign.sign_blob(blob, key, head="agri", n_classes=5, classes=list("abcde"))
    blob.write_bytes(blob.read_bytes() + b"\x00")  # flip one byte of content
    ok, reason = sign.verify(blob, att)
    assert not ok and "sha256" in reason


def test_tampered_metadata_rejected():
    tmp = Path(tempfile.mkdtemp())
    blob = _blob(tmp)
    key = sign.generate_key()
    att = sign.sign_blob(blob, key, head="agri", n_classes=5, classes=list("abcde"))
    att["receipt"]["head"] = "evil"  # lie about which head this is
    ok, reason = sign.verify(blob, att)
    assert not ok


def test_forged_signature_rejected():
    tmp = Path(tempfile.mkdtemp())
    blob = _blob(tmp)
    key = sign.generate_key()
    att = sign.sign_blob(blob, key, head="agri", n_classes=5, classes=list("abcde"))
    att["signature"] = "00" * 64
    ok, reason = sign.verify(blob, att)
    assert not ok

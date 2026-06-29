"""Model-zoo: registry build/list, verified pull, tamper-reject."""
import json
import tempfile
from pathlib import Path

import pytest

from superesp.zoo import registry as z

_HAS_ART = (z.ART / "RESULTS.json").exists() and any(z.ART.glob("*.atomecl"))


@pytest.mark.skipif(not _HAS_ART, reason="no trained artifacts present")
def test_build_and_list():
    m = z.build_registry()
    assert m["heads"] and all("sha256" in h and "intended_use" in h for h in m["heads"])
    names = {h["name"] for h in z.list_heads()}
    assert "agri" in names


@pytest.mark.skipif(not _HAS_ART, reason="no trained artifacts present")
def test_pull_verifies_then_installs():
    z.build_registry()
    dest = Path(tempfile.mkdtemp())
    r = z.pull("agri", dest)
    assert r["ok"] and r["verified"]
    assert (dest / "agri.atomecl").exists()


@pytest.mark.skipif(not _HAS_ART, reason="no trained artifacts present")
def test_publish_then_pull_verified_then_cleanup():
    blob = next(z.ART.glob("*.atomecl"))
    try:
        r = z.publish(blob, "zootest_tmp", ["a", "b"], "unit-test", source="USER")
        assert r["ok"]
        names = {h["name"] for h in z.list_heads()}
        assert "zootest_tmp" in names
        idx = z.index_html(); assert Path(idx).exists()
        pr = z.pull("zootest_tmp", Path(tempfile.mkdtemp()))
        assert pr["ok"] and pr["verified"]
    finally:
        for f in z.STORE.glob("zootest_tmp.*"):
            f.unlink()
        z.build_registry()


@pytest.mark.skipif(not _HAS_ART, reason="no trained artifacts present")
def test_pull_rejects_sha_mismatch():
    z.build_registry()
    orig = z.MANIFEST.read_text()
    bad = json.loads(orig)
    for h in bad["heads"]:
        if h["name"] == "agri":
            h["sha256"] = "0" * 64
    z.MANIFEST.write_text(json.dumps(bad))
    try:
        r = z.pull("agri", Path(tempfile.mkdtemp()))
        assert not r["ok"] and "sha256" in r["reason"]
    finally:
        z.MANIFEST.write_text(orig)

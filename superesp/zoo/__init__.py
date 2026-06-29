"""superesp.zoo — a signed, verifiable head registry (the distribution seed).

Heads are shared as: the ATOMECL01 blob + a model card + an Ed25519 attestation.
A registry.json manifest lists each head with its sha256 + classes + intended use
+ attestation. `pull` copies a head and VERIFIES (sha256 + signature) before
installing — so a community/model-zoo can distribute heads that a device can
trust. Local paths here; remote URLs are a drop-in (fetch then same verify).
"""

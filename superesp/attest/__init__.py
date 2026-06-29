"""superesp.attest — sign + verify head binaries (the auditability angle).

The only surviving moat *candidate* for Atome (per the 2026-06-13 review) is
"the on-chip model you can audit byte-for-byte AND cryptographically attest".
This module gives each ATOMECL01 head a signed receipt binding sha256(blob) +
metadata under an Ed25519 key, so a deployer can prove THIS exact head ran on
the device. Reuses the same primitive as Atome's secure envelope (Ed25519).
"""

# KOD8 Sandbox Edition (v3.0)

KOD8 is a unified, NCIA-compliant cryptographic engine and split-key provisioning tool designed for secure facility operations. 

In v3.0, the legacy obfuscation pipelines have been completely replaced with FIPS-validated primitives, executing as a state machine governed by the topological trace of the facility key (`86247931`).

## Core Capabilities

1. **File & Text Encryptor (CL1–CL8)**
   * **AES-256-GCM** authenticated bulk encryption.
   * **HKDF-SHA-384** key expansion using unique per-file salts.
   * Integrated **Zlib Deflate** and **SHA-512** outer-integrity hashing.
   * Optional OpenPGP detached signing (`.asc`) for non-repudiation.

2. **Split-Key Disk Provisioner (CL9)**
   * **Zero-Trust USB Security:** Replaces passphrases and telemetry lockouts.
   * Derives native AES-XTS bootloader keys (`.bek` for BitLocker, raw binary for LUKS2) by cryptographically fusing a physical drive token (Volume A) with a secure Host PC enclave token.
   * The drive is inaccessible without the authorized host machine.

## Deployment & Usage

KOD8 requires zero external dependencies beyond standard cryptographic libraries.

**Install requirements:**
```bash
pip install cryptography psutil PGPy13

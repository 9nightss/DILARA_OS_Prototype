# DILARA per-user vault and virtual root (prototype)

## Current behavior

- Every DILARA account receives one `vaults/<random-account-id>.dvault` container. Existing account records are assigned a random vault ID on first successful login; the username is not used directly in the filename.
- On successful login, the supplied password is transformed using the mapping from `BINARY_2_DNA.sh` (`00=A`, `01=C`, `10=G`, `11=T`), then represented as hexadecimal DNA text.
- The transformed bytes are input to PBKDF2-HMAC-SHA256 with a random per-vault salt and 600,000 iterations. The resulting 256-bit key is held in memory for the session; the password and DNA/hex intermediate are not written to disk.
- The virtual root is archived as ZIP bytes in memory, then encrypted using AES-256-GCM from the `cryptography` package. The container contains a version marker, salt, nonce, and authenticated ciphertext. It does not contain a plaintext ZIP.
- The `FILES` workspace browses the unlocked tree and can create folders and UTF-8 text files, then edit/save text files.
- The custom browser profile is placed under `Applications/Browser` in the virtual root so it is included in the vault.
- On sign-out or shutdown, DILARA requests that the browser be closed first, archives and encrypts the root, atomically replaces the container, keeps one active encrypted container per user, then removes the session workspace.
- An incorrect password or authentication-tag failure prevents the vault from opening. A failed commit leaves the desktop session open for retry.

## Initial virtual root

```text
/
├── Desktop/
├── Documents/
│   └── Welcome.txt
├── Applications/
│   ├── Browser/
│   └── Notepad/
├── D-LLM/
├── D-ARCADE/
├── Workspace/
└── Recycle Bin/
```

Per-user desktop layout, DSPACE/CYBERSTORM/EYE resource lists, and the added-app registry are stored under `Applications/` in the vault. The local account database (`config/users.json`) and the existing global KOD8 activity log remain outside the per-user vault by design. Registered application code and other external files are not copied into the vault merely because a manifest references them. External child processes other than the browser are not yet universally coordinated with vault shutdown.

## Security and recovery limitations

- DNA and hexadecimal conversion are reversible encodings, not encryption. The salt and PBKDF2 step provide password-based key derivation; AES-GCM provides confidentiality and integrity for the container.
- The password is used both for local account authentication and vault unlocking in this prototype. A future account-password-change/recovery workflow is required before changing passwords is supported.
- The unlocked directory is a plaintext staging workspace under `runtime/active_vaults/`. This is a prototype compromise for compatibility with ordinary Windows/Python apps. It is not a virtual filesystem, and a local Windows administrator can access the files. Windows ACLs and full-disk encryption are recommended.
- An abrupt process termination or power loss can leave plaintext staging files behind and may lose edits since the last successful seal. Do not force-kill DILARA during save/seal. Crash-recovery and stale-session detection are not yet implemented; inspect and secure `runtime/active_vaults/` after a crash before continuing.
- Automatic backup is intentionally disabled to preserve the one-container-per-user design. Make a manual copy of a sealed `.dvault` file to a separate safe destination if you need backup/recovery.
- The current KOD8 CL1–CL8 pipeline is not used to encrypt vault containers. It remains separate for its existing activity-log integration and standalone experimental UI.
- Browser profile data is included in the root, so DILARA blocks normal sign-out while its tracked browser process is still running. Cross-process graceful close coordination is not yet implemented.
- This prototype has not undergone a security audit. Do not treat it as a hardened OS or high-assurance vault.

## Tests

Run from the project root:

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m unittest discover -s tests -v
```

The tests cover DNA mapping and round-trips, per-user vault isolation, wrong-password rejection, ciphertext tamper rejection, and file persistence across seal/unlock cycles. They do not replace runtime testing on Windows.

# KOD8 and DILARA activity logging

## Chosen project behaviour

- Preserve the existing `KOD8_ENC/kod8_engine.py`, `kod8_ui.py`, and all strategy IDs CL1–CL8.
- Keep the existing KOD8 UI as a separate side application, launched from the KOD8 workspace.
- Keep the DILARA activity-log interface in `services/activity_log.py`; it does not import or call the experimental engine directly.
- Bridge the interface to the existing engine only through `services/kod8_adapter.py`.
- Current shell activity events are encrypted using CL1 and written as JSON-line envelopes to `data/activity.kod8log`. The envelope stores the strategy ID so the matching reverse pipeline can be selected later.
- If encryption or writing fails, the logger raises an error and does not silently write plaintext. The shell remains usable and reports the failure to stderr.

## Security limitation (explicit)

This follows the user's decision to use the existing KOD8 pipeline as-is, with limitations documented. The current implementation contains a hardcoded key (`b"86247931"`) and several operations are simple reversible transforms rather than the cryptographic algorithms suggested by their names. The current pipeline does not provide authenticated encryption, integrity verification, or tamper evidence. Therefore:

- Treat the activity log as experimental obfuscation/encryption, not as a security boundary for secrets or high-assurance audit records.
- Do not place passwords, tokens, raw command contents, or other secrets in activity-event details.
- Restrict access to the application directory and the log file at the filesystem level.
- Keep the warning in each envelope; do not label these records as tamper-proof.
- No automatic key migration or algorithm substitution is performed.

## Interface

`ActivityLogger.record(event, module, details=None)` accepts operational metadata and delegates string encryption to a `TextCipher` protocol. The KOD8 adapter is replaceable without changing module code. The default logging strategy is CL1; the side app retains CL1–CL8.

## Verification

Run from the project root:

```powershell
python -m unittest discover -s tests -v
```

The tests verify round-trip compatibility for CL1–CL8 and confirm that the log writer emits an encrypted envelope rather than a plaintext event field. They do not establish cryptographic security.

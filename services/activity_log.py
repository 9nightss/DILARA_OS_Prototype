"""Activity-log interface; independent of KOD8's experimental pipeline internals.

Log entries contain operational metadata only. The KOD8 backend is injected so
that callers depend on this interface, not on the cipher engine implementation.
This log format provides no cryptographic authenticity or tamper detection.
"""
from __future__ import annotations
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

class TextCipher(Protocol):
    def encrypt_text(self, text: str, strategy_id: str = "CL1") -> tuple[str, str]: ...

class ActivityLogError(RuntimeError):
    pass

class ActivityLogger:
    def __init__(self, path: Path, cipher: TextCipher, strategy_id: str = "CL1"):
        self.path = Path(path)
        self.cipher = cipher
        self.strategy_id = strategy_id
        self._lock = threading.Lock()

    def record(self, event: str, module: str = "SYSTEM", details: dict | None = None) -> None:
        """Encrypt and append one metadata event; never silently write plaintext."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "event": str(event)[:120],
            "module": str(module)[:80],
            "details": details or {},
        }
        try:
            payload = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            cid, ciphertext = self.cipher.encrypt_text(payload, self.strategy_id)
            envelope = {
                "format": "DILARA-KOD8-ACTIVITY-1",
                "cipher_id": cid,
                "ciphertext": ciphertext,
                "warning": "Experimental KOD8 output; not authenticated or tamper-evident",
            }
            line = json.dumps(envelope, ensure_ascii=True, separators=(",", ":")) + "\n"
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, self.path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(line)
        except Exception as exc:
            raise ActivityLogError(f"Activity event was not logged: {exc}") from exc

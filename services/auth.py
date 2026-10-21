"""Local multi-user authentication for the DILARA prototype.

Passwords are stored as PBKDF2-HMAC-SHA256 verifiers, never plaintext. This is
local application authentication, not Windows account authentication or a
security boundary against another administrator on the same machine.
"""
from __future__ import annotations
import hashlib, hmac, json, os, re
from pathlib import Path

ITERATIONS = 310_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")

class AuthError(ValueError): pass

class UserStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists(): self._write({"version": 1, "users": {}})

    def _read(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") != 1 or not isinstance(data.get("users"), dict): raise ValueError
            return data
        except (OSError, json.JSONDecodeError, ValueError, AttributeError) as exc:
            raise AuthError(f"User database is unreadable: {exc}") from exc

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try: os.chmod(temp, 0o600)
        except OSError: pass
        temp.replace(self.path)

    def users(self): return self._read()["users"]
    def has_users(self): return bool(self.users())

    @staticmethod
    def validate_username(username):
        if not USERNAME_RE.fullmatch(username or ""):
            raise AuthError("Username must be 3–32 characters: letters, numbers, dot, underscore or hyphen.")

    def create_user(self, username, password, role="user"):
        username = (username or "").strip()
        self.validate_username(username)
        if len(password or "") < 10: raise AuthError("Password must contain at least 10 characters.")
        if role not in ("admin", "user"): raise AuthError("Invalid role.")
        data = self._read()
        if username.casefold() in {u.casefold() for u in data["users"]}: raise AuthError("That username already exists.")
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
        data["users"][username] = {"salt": salt.hex(), "verifier": digest.hex(), "iterations": ITERATIONS, "role": role, "enabled": True}
        self._write(data)
        return {"username": username, "role": role}

    def authenticate(self, username, password):
        data = self._read()
        found = next((k for k in data["users"] if k.casefold() == (username or "").casefold()), None)
        if not found: return None
        rec = data["users"][found]
        if not rec.get("enabled", True): return None
        try:
            actual = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), bytes.fromhex(rec["salt"]), int(rec["iterations"]))
            valid = hmac.compare_digest(actual.hex(), rec["verifier"])
        except (ValueError, KeyError, TypeError): return None
        return {"username": found, "role": rec.get("role", "user")} if valid else None

    def set_enabled(self, username, enabled):
        data = self._read()
        if username not in data["users"]: raise AuthError("User not found.")
        if data["users"][username].get("role") == "admin" and not enabled:
            admins = [u for u in data["users"].values() if u.get("role") == "admin" and u.get("enabled", True)]
            if len(admins) <= 1: raise AuthError("Cannot disable the last administrator.")
        data["users"][username]["enabled"] = bool(enabled); self._write(data)

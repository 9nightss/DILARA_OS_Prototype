"""Per-user single-file vault prototype for DILARA.

The password is transformed with the DNA mapping from the supplied reference,
then passed through PBKDF2-HMAC-SHA256. AES-GCM authenticates the encrypted ZIP
container. DNA/hex is a representation only, not cryptographic protection.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .dna_codec import password_to_hex

MAGIC = b"DVL1"
SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32
KDF_ITERATIONS = 600_000
AAD = b"DILARA-DVAULT-v1"


class VaultError(RuntimeError):
    """Raised for vault unlock, integrity, archive or commit failures."""


def _user_token(username: str, vault_id: str | None = None) -> str:
    # Prefer the random stable account ID. The hash fallback supports standalone
    # service tests and older callers that have not supplied an account record.
    if vault_id and re.fullmatch(r"[0-9a-f]{32}", vault_id):
        return vault_id
    return hashlib.sha256(username.casefold().encode("utf-8")).hexdigest()[:32]


def _derive_key(password: str, salt: bytes) -> bytes:
    if not password:
        raise VaultError("Vault password cannot be empty.")
    transformed = password_to_hex(password).encode("ascii")
    return hashlib.pbkdf2_hmac("sha256", transformed, salt, KDF_ITERATIONS, dklen=KEY_BYTES)


class VaultManager:
    """Own one user's unlocked tree and atomically seal it to one .dvault file."""

    def __init__(self, app_dir: Path, username: str, vault_id: str | None = None):
        self.app_dir = Path(app_dir).resolve()
        self.username = username
        token = _user_token(username, vault_id)
        self.vault_dir = self.app_dir / "vaults"
        self.vault_path = self.vault_dir / f"{token}.dvault"
        self.runtime_dir = self.app_dir / "runtime" / "active_vaults"
        self.root: Path | None = None
        self._session_dir: Path | None = None
        self._salt: bytes | None = None
        self._key: bytes | None = None
        self.is_open = False

    def unlock(self, password: str) -> Path:
        if self.is_open:
            return self.root  # type: ignore[return-value]
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._session_dir = Path(tempfile.mkdtemp(prefix="dilara-vault-", dir=self.runtime_dir))
            try:
                os.chmod(self._session_dir, 0o700)
            except OSError:
                pass
            self.root = self._session_dir / "root"
            self.root.mkdir()
            if self.vault_path.exists():
                archive, self._salt, self._key = self._decrypt_container(self.vault_path.read_bytes(), password)
                self._extract_archive(archive, self.root)
            else:
                self._salt = os.urandom(SALT_BYTES)
                self._key = _derive_key(password, self._salt)
                self._create_default_tree(self.root)
                # First login initializes the encrypted container but leaves the
                # current plaintext workspace open for the user's session.
                self._commit()
            self.is_open = True
            return self.root
        except Exception:
            self._cleanup_workspace()
            self.root = None
            self._salt = None
            self._key = None
            self.is_open = False
            raise

    def seal(self) -> None:
        if not self.is_open or self.root is None:
            return
        self._commit()
        self._cleanup_workspace()
        self.root = None
        self._salt = None
        self._key = None
        self.is_open = False

    def _create_default_tree(self, root: Path) -> None:
        for relative in (
            "Documents", "Desktop", "Applications", "Applications/Notepad",
            "Applications/Browser", "D-LLM", "D-ARCADE", "Workspace", "Recycle Bin",
        ):
            (root / relative).mkdir(parents=True, exist_ok=True)
        welcome = root / "Documents" / "Welcome.txt"
        welcome.write_text(
            "Welcome to DILARA.\n\nThis is your private virtual root directory. "
            "Files saved here are included in your per-user vault.\n",
            encoding="utf-8",
        )

    def _archive_root(self) -> bytes:
        if self.root is None or not self.root.is_dir():
            raise VaultError("The active vault root is unavailable.")
        output = io.BytesIO()
        try:
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                for path in sorted(self.root.rglob("*")):
                    if path.is_symlink():
                        raise VaultError(f"Symbolic links are not supported inside the vault: {path.name}")
                    arcname = path.relative_to(self.root).as_posix()
                    if path.is_dir():
                        zf.writestr(arcname.rstrip("/") + "/", b"")
                    elif path.is_file():
                        zf.write(path, arcname)
        except (OSError, zipfile.BadZipFile) as exc:
            raise VaultError(f"Could not archive the user directory: {exc}") from exc
        return output.getvalue()

    def _encrypt_container(self, archive: bytes) -> bytes:
        if self._salt is None or self._key is None:
            raise VaultError("Vault key material is not available in this session.")
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(self._key).encrypt(nonce, archive, AAD)
        # Fixed magic/version, per-vault salt, fresh nonce, then authenticated ciphertext.
        return MAGIC + self._salt + nonce + ciphertext

    def _decrypt_container(self, payload: bytes, password: str) -> tuple[bytes, bytes, bytes]:
        minimum = len(MAGIC) + SALT_BYTES + NONCE_BYTES + 16
        if len(payload) < minimum or not payload.startswith(MAGIC):
            raise VaultError("Vault container is invalid or uses an unsupported version.")
        offset = len(MAGIC)
        salt = payload[offset:offset + SALT_BYTES]; offset += SALT_BYTES
        nonce = payload[offset:offset + NONCE_BYTES]; offset += NONCE_BYTES
        key = _derive_key(password, salt)
        try:
            archive = AESGCM(key).decrypt(nonce, payload[offset:], AAD)
            return archive, salt, key
        except InvalidTag as exc:
            raise VaultError("Vault unlock failed: incorrect password or damaged container.") from exc

    def _commit(self) -> None:
        archive = self._archive_root()
        encrypted = self._encrypt_container(archive)
        temp_path = self.vault_path.with_suffix(".dvault.tmp")
        try:
            with temp_path.open("wb") as handle:
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            # Same-volume atomic replacement means the prior container remains in
            # place if writing/encryption fails before this point. Exactly one
            # active container is retained per user; backups are user-managed.
            os.replace(temp_path, self.vault_path)
        except OSError as exc:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise VaultError(f"Could not commit encrypted vault: {exc}") from exc

    @staticmethod
    def _extract_archive(archive: bytes, destination: Path) -> None:
        try:
            with zipfile.ZipFile(io.BytesIO(archive), "r") as zf:
                for member in zf.infolist():
                    name = member.filename.replace("\\", "/")
                    pure = PurePosixPath(name)
                    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                        raise VaultError("Vault archive contains an unsafe path.")
                    target = (destination / Path(*pure.parts)).resolve()
                    if not target.is_relative_to(destination.resolve()):
                        raise VaultError("Vault archive path escapes the virtual root.")
                    # Reject Unix symbolic-link entries instead of extracting them.
                    if (member.external_attr >> 16) & 0o170000 == 0o120000:
                        raise VaultError("Symbolic links are not supported inside the vault.")
                    if member.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member, "r") as source, target.open("wb") as output:
                            shutil.copyfileobj(source, output)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            if isinstance(exc, VaultError):
                raise
            raise VaultError(f"Vault archive could not be opened: {exc}") from exc

    def _cleanup_workspace(self) -> None:
        if self._session_dir and self._session_dir.exists():
            try:
                shutil.rmtree(self._session_dir)
            except OSError as exc:
                # Do not pretend plaintext workspace cleanup succeeded.
                raise VaultError(f"Vault was sealed, but its temporary workspace could not be removed: {exc}") from exc
        self._session_dir = None

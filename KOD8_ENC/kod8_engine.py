#!/usr/bin/env python3
# =============================================================================
# KOD 8  (corrected backend)
# =============================================================================
# Fixes vs. original:
#   1. op_turkish_normalize was lossy: decrypt turned EVERY ASCII c/g/i/o/s/u
#      (and C/G/I/O/S/U) into a Turkish letter. Now uses a reversible
#      escape scheme ("~" + letter, with "~" escaped as "~~").
#   2. op_galois_field_mult crashed on decrypt whenever the derived multiplier
#      was even (no inverse mod 256). Multiplier is now forced odd. The value
#      for the current key (57) is unchanged. NOTE: this is multiplication
#      mod 256, not GF(2^8); the comment now says so.
#   3. Decrypt silently decoded with errors="replace", hiding wrong-key /
#      wrong-list failures as corrupted text. Now strict + clear ValueError.
#   4. Decrypt without list_id silently fell back to CL1 (ciphertext is
#      base64, so detection can never work). Now raises instead of returning
#      garbage.
#   5. base64 decoding is validated (validate=True) so malformed input fails
#      loudly instead of being silently stripped.
#   6. _detect_numeric used str.isdigit(), which accepts non-ASCII digits
#      such as "²"; now ASCII-only.
#   7. Comment fixes: "p=257 affine" op is really a +13 shift mod 256.
# =============================================================================

import base64
import hashlib

# ── Global Key Config ────────────────────────────────────────────────────────
KOD8_KEY = b"86247931"


# ── Helper Detection Functions ───────────────────────────────────────────────
def _detect_turkish(text: str) -> bool:
    turkish_chars = set("çğıöşüÇĞİÖŞÜ")
    return any(c in turkish_chars for c in text)


def _detect_numeric(text: str) -> bool:
    t = text.strip()
    return t.isascii() and t.isdigit()


# ── Shared byte-level helpers ────────────────────────────────────────────────
def _to_bytes(data: str, encrypt: bool) -> bytes:
    if encrypt:
        return data.encode("utf-8")
    try:
        return base64.b64decode(data, validate=True)
    except Exception as e:
        raise ValueError(f"KOD8: ciphertext is not valid base64 at this stage "
                         f"(wrong list_id or corrupted input): {e}") from None


def _from_bytes(out: bytes, encrypt: bool) -> str:
    if encrypt:
        return base64.b64encode(bytes(out)).decode("ascii")
    try:
        return bytes(out).decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"KOD8: decrypted bytes are not valid UTF-8 "
                         f"(wrong key/list_id or corrupted input): {e}") from None


def _xor_stream(data: str, stream: bytes, encrypt: bool) -> str:
    raw = _to_bytes(data, encrypt)
    return _from_bytes(bytearray(b ^ stream[i % len(stream)] for i, b in enumerate(raw)), encrypt)


def _add_shift(data: str, n: int, encrypt: bool) -> str:
    raw = _to_bytes(data, encrypt)
    return _from_bytes(bytearray(((b + n) if encrypt else (b - n)) % 256 for b in raw), encrypt)


# ── Primitive Operations ─────────────────────────────────────────────────────
def op_mlkem_encap(data: str, key: bytes, encrypt: bool = True) -> str:
    # (Label only: SHA-256-derived repeating XOR keystream, not ML-KEM.)
    return _xor_stream(data, hashlib.sha256(key).digest(), encrypt)


def op_blake3_seed_prep(data: str, key: bytes, encrypt: bool = True) -> str:
    # (Label only: BLAKE2b-128-derived repeating XOR keystream.)
    return _xor_stream(data, hashlib.blake2b(key, digest_size=16).digest(), encrypt)


# Reversible Turkish normalization: "~" is the escape character.
_TR_MAP = {"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
           "Ç": "C", "Ğ": "G", "İ": "I", "Ö": "O", "Ş": "S", "Ü": "U"}
_TR_INV = {v: k for k, v in _TR_MAP.items()}


def op_turkish_normalize(data: str, key: bytes, encrypt: bool = True) -> str:
    if encrypt:
        out = []
        for c in data:
            if c == "~":
                out.append("~~")
            elif c in _TR_MAP:
                out.append("~" + _TR_MAP[c])
            else:
                out.append(c)
        return "".join(out)
    out, i, n = [], 0, len(data)
    while i < n:
        c = data[i]
        if c != "~":
            out.append(c)
            i += 1
            continue
        if i + 1 >= n:
            raise ValueError("KOD8: dangling escape in Turkish-normalized text")
        nxt = data[i + 1]
        if nxt == "~":
            out.append("~")
        elif nxt in _TR_INV:
            out.append(_TR_INV[nxt])
        else:
            raise ValueError(f"KOD8: invalid escape '~{nxt}' in Turkish-normalized text")
        i += 2
    return "".join(out)


def op_rocca_s_stream(data: str, key: bytes, encrypt: bool = True) -> str:
    # (Label only: SHA-512-derived repeating XOR keystream.)
    return _xor_stream(data, hashlib.sha512(key).digest(), encrypt)


def op_galois_field_mult(data: str, key: bytes, encrypt: bool = True) -> str:
    # Multiplication mod 256 (NOT GF(2^8)). Multiplier must be odd to be invertible.
    mult = (key[0] % 254) + 1
    if mult % 2 == 0:
        mult += 1                      # 2..254 -> 3..255, always odd, <= 255
    inv = pow(mult, -1, 256)
    raw = _to_bytes(data, encrypt)
    k = mult if encrypt else inv
    return _from_bytes(bytearray((b * k) % 256 for b in raw), encrypt)


def op_dynamic_split(data: str, key: bytes, encrypt: bool = True) -> str:
    if len(data) < 2:
        return data
    mid = len(data) // 2
    if encrypt:
        return data[mid:] + data[:mid]
    rem = len(data) - mid
    return data[rem:] + data[:rem]


def op_base36_pack(data: str, key: bytes, encrypt: bool = True) -> str:
    # (Label only: +36 byte shift mod 256.)
    return _add_shift(data, 36, encrypt)


def op_glevian_block(data: str, key: bytes, encrypt: bool = True) -> str:
    return _xor_stream(data, b"\xAA", encrypt)


def op_vigornian_sub(data: str, key: bytes, encrypt: bool = True) -> str:
    return _add_shift(data, 7, encrypt)


def op_aegis256x(data: str, key: bytes, encrypt: bool = True) -> str:
    # (Label only: SHA-256(key+"_aegis") repeating XOR keystream.)
    return _xor_stream(data, hashlib.sha256(key + b"_aegis").digest(), encrypt)


def op_prime_affine_transform(data: str, key: bytes, encrypt: bool = True) -> str:
    # (Label only: +13 byte shift mod 256, not a p=257 affine map.)
    return _add_shift(data, 13, encrypt)


def op_ascon128_sponge(data: str, key: bytes, encrypt: bool = True) -> str:
    # (Label only: MD5-derived repeating XOR keystream.)
    return _xor_stream(data, hashlib.md5(key).digest(), encrypt)


def op_full_reverse(data: str, key: bytes, encrypt: bool = True) -> str:
    return data[::-1]


# ── Strategy Matrix Definition (CL1 - CL8) ──────────────────────────────────
CIPHER_LISTS = {
    "CL1": {"name": "ASCII PLAIN TEXT", "steps": [
        (op_mlkem_encap, True), (op_rocca_s_stream, True), (op_dynamic_split, True),
        (op_glevian_block, True), (op_vigornian_sub, True), (op_aegis256x, True),
        (op_ascon128_sponge, True), (op_full_reverse, True)]},
    "CL2": {"name": "NUMERIC STRINGS", "steps": [
        (op_blake3_seed_prep, True), (op_galois_field_mult, True), (op_base36_pack, True),
        (op_glevian_block, True), (op_vigornian_sub, True), (op_prime_affine_transform, True),
        (op_ascon128_sponge, True), (op_full_reverse, True)]},
    "CL3": {"name": "DOCUMENT FILES", "steps": [
        (op_mlkem_encap, True), (op_rocca_s_stream, True), (op_base36_pack, True),
        (op_glevian_block, True), (op_vigornian_sub, True), (op_aegis256x, True),
        (op_ascon128_sponge, True), (op_full_reverse, True)]},
    "CL4": {"name": "IMAGE DATA", "steps": [
        (op_blake3_seed_prep, True), (op_rocca_s_stream, True), (op_dynamic_split, True),
        (op_glevian_block, True), (op_vigornian_sub, True), (op_aegis256x, True),
        (op_ascon128_sponge, True), (op_full_reverse, True)]},
    "CL5": {"name": "VIDEO DATA", "steps": [
        (op_mlkem_encap, True), (op_galois_field_mult, True), (op_dynamic_split, True),
        (op_glevian_block, True), (op_vigornian_sub, True), (op_prime_affine_transform, True),
        (op_ascon128_sponge, True), (op_full_reverse, True)]},
    "CL6": {"name": "FALLBACK ENGINE 1", "steps": [
        (op_blake3_seed_prep, True), (op_rocca_s_stream, True), (op_base36_pack, True),
        (op_glevian_block, True), (op_vigornian_sub, True), (op_prime_affine_transform, True),
        (op_ascon128_sponge, True), (op_full_reverse, True)]},
    "CL7": {"name": "FALLBACK ENGINE 2", "steps": [
        (op_mlkem_encap, True), (op_galois_field_mult, True), (op_base36_pack, True),
        (op_glevian_block, True), (op_vigornian_sub, True), (op_aegis256x, True),
        (op_ascon128_sponge, True), (op_full_reverse, True)]},
    "CL8": {"name": "TURKISH SPECIAL CHARS", "steps": [
        (op_turkish_normalize, True), (op_rocca_s_stream, True), (op_dynamic_split, True),
        (op_glevian_block, True), (op_vigornian_sub, True), (op_aegis256x, True),
        (op_ascon128_sponge, True), (op_full_reverse, True)]},
}


# ── Pipeline Execution Entry Point ───────────────────────────────────────────
def run_kod8_pipeline(text: str, is_file: bool = False, encrypt: bool = True,
                      list_id: str = None, key: bytes = None) -> tuple:
    """
    Executes the 8-step transform pipeline for the specified strategy list.
    Encrypt: list_id is auto-detected if omitted.
    Decrypt: list_id is REQUIRED (ciphertext carries no hint about its list).
    Returns: (strategy_id, resulting_text, history_log)
    """
    key = KOD8_KEY if key is None else key

    if list_id is not None and list_id not in CIPHER_LISTS:
        raise ValueError(f"KOD8: unknown list_id {list_id!r}")
    if list_id is None:
        if not encrypt:
            raise ValueError("KOD8: list_id is required for decryption")
        if _detect_turkish(text):
            list_id = "CL8"
        elif _detect_numeric(text):
            list_id = "CL2"
        else:
            list_id = "CL1"

    steps = CIPHER_LISTS[list_id]["steps"]
    pipeline = steps if encrypt else list(reversed(steps))
    current = text
    history = []
    for fn, enabled in pipeline:
        if enabled:
            current = fn(current, key, encrypt=encrypt)
            history.append((fn.__name__, current))
    return list_id, current, history
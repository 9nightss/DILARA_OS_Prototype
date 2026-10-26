"""Binary <-> DNA text codec based on the supplied BINARY_2_DNA.sh reference.

Mapping from the reference: 00=A, 01=C, 10=G, 11=T.
This is a reversible representation, not encryption. ``password_to_hex`` exists
as a deterministic input transform for a subsequent password KDF; never store its
output as a password verifier or as a standalone secret.
"""
from __future__ import annotations

from typing import Final

BITS_TO_BASE: Final[dict[str, str]] = {
    "00": "A",
    "01": "C",
    "10": "G",
    "11": "T",
}
BASE_TO_BITS: Final[dict[str, str]] = {base: bits for bits, base in BITS_TO_BASE.items()}


class DNAEncodingError(ValueError):
    """Raised when DNA data is malformed or cannot be decoded."""


def bytes_to_binary(data: bytes) -> str:
    """Return each byte as exactly eight binary digits."""
    return "".join(f"{value:08b}" for value in data)


def binary_to_dna(binary: str) -> str:
    """Translate a binary string using the reference's two-bit mapping."""
    if any(bit not in "01" for bit in binary):
        raise DNAEncodingError("Binary input may contain only 0 and 1.")
    if len(binary) % 2:
        raise DNAEncodingError("Binary input length must be divisible by two.")
    return "".join(BITS_TO_BASE[binary[i:i + 2]] for i in range(0, len(binary), 2))


def dna_to_binary(sequence: str) -> str:
    """Reverse the two-bit DNA mapping."""
    sequence = sequence.upper()
    if any(base not in BASE_TO_BITS for base in sequence):
        raise DNAEncodingError("DNA sequence may contain only A, C, G and T.")
    return "".join(BASE_TO_BITS[base] for base in sequence)


def binary_to_bytes(binary: str) -> bytes:
    """Convert a byte-aligned binary string back into bytes."""
    if any(bit not in "01" for bit in binary):
        raise DNAEncodingError("Binary input may contain only 0 and 1.")
    if len(binary) % 8:
        raise DNAEncodingError("Binary input length must be divisible by eight.")
    return bytes(int(binary[i:i + 8], 2) for i in range(0, len(binary), 8))


def dna_to_hex(sequence: str) -> str:
    """Hex-encode the ASCII bytes of a DNA sequence (e.g. ACGT -> 41434754)."""
    sequence = sequence.upper()
    if any(base not in BASE_TO_BITS for base in sequence):
        raise DNAEncodingError("DNA sequence may contain only A, C, G and T.")
    return sequence.encode("ascii").hex()


def hex_to_dna(encoded_hex: str) -> str:
    """Reverse :func:`dna_to_hex`, rejecting malformed or non-DNA content."""
    try:
        sequence = bytes.fromhex(encoded_hex).decode("ascii")
    except (ValueError, UnicodeDecodeError) as exc:
        raise DNAEncodingError("Hex value is not valid hexadecimal DNA text.") from exc
    sequence = sequence.upper()
    if any(base not in BASE_TO_BITS for base in sequence):
        raise DNAEncodingError("Hex value does not decode to A/C/G/T DNA text.")
    return sequence


def encode_bytes(data: bytes) -> str:
    """Encode arbitrary bytes as the reference DNA mapping's hex representation."""
    return dna_to_hex(binary_to_dna(bytes_to_binary(data)))


def decode_bytes(encoded_hex: str) -> bytes:
    """Decode a value produced by :func:`encode_bytes` back to the original bytes."""
    return binary_to_bytes(dna_to_binary(hex_to_dna(encoded_hex)))


def password_to_hex(password: str) -> str:
    """Encode a password using UTF-8 -> binary -> DNA -> hex.

    This is only a reversible pre-KDF transform. The caller must pass the result
    to a salted, deliberately expensive password-based KDF before using it as key
    material for encryption.
    """
    if not isinstance(password, str):
        raise TypeError("Password must be text.")
    return encode_bytes(password.encode("utf-8"))

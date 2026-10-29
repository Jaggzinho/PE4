from __future__ import annotations

import hashlib
import hmac
import os


PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, *, salt: bytes | None = None) -> tuple[bytes, bytes]:
    if salt is None:
        salt = os.urandom(16)
    pw = password.encode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", pw, salt, PBKDF2_ITERATIONS, dklen=32)
    return salt, dk


def verify_password(password: str, *, salt: bytes, expected_hash: bytes) -> bool:
    _salt, dk = hash_password(password, salt=salt)
    return hmac.compare_digest(dk, expected_hash)


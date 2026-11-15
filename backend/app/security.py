"""Password hashing (scrypt, salted) with transparent upgrade of legacy hashes."""
import hashlib
import hmac
import os
import re
from typing import Tuple

from backend.app.config import settings

_N, _R, _P = 2 ** 14, 8, 1
_SCRYPT_PREFIX = "scrypt$"
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, maxmem=64 * 1024 * 1024, dklen=32)
    return f"{_SCRYPT_PREFIX}{_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> Tuple[bool, bool]:
    """Return (is_valid, needs_upgrade). needs_upgrade means the stored hash should be re-written with scrypt."""
    if not stored:
        return False, False
    if stored.startswith(_SCRYPT_PREFIX):
        try:
            _, n, r, p, salt_hex, hash_hex = stored.split("$")
            dk = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r),
                                p=int(p), maxmem=64 * 1024 * 1024, dklen=len(hash_hex) // 2)
        except (ValueError, TypeError):
            return False, False
        return hmac.compare_digest(dk.hex(), hash_hex), False
    if _SHA256_HEX.match(stored):  # legacy unsalted SHA-256
        ok = hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), stored)
        return ok, ok
    # Legacy plaintext seeds (demo databases only). Never accepted when DEMO_MODE is off.
    if settings.DEMO_MODE:
        ok = hmac.compare_digest(password.encode("utf-8"), stored.encode("utf-8"))
        return ok, ok
    return False, False

import base64
import binascii
import hashlib
import itertools
from typing import Any, Callable, Optional


def _check(digest: bytes, difficulty: int) -> bool:
    required_zero_bits = difficulty
    for byte in digest:
        if required_zero_bits <= 0:
            break
        if required_zero_bits >= 8:
            if byte != 0:
                return False
            required_zero_bits -= 8
        else:
            mask = 0xFF << (8 - required_zero_bits)
            if byte & mask != 0:
                return False
            required_zero_bits = 0
    return True


def hash_pow(challenge: str, salt: str, difficulty: int, **kwargs) -> Optional[str]:
    prefix = (challenge + salt).encode()
    for nonce in itertools.count():
        digest = hashlib.sha256(prefix + str(nonce).encode()).digest()
        if _check(digest, difficulty):
            return str(nonce)
    return None


def scrypt_func(input_str: str, salt: str, n: int = 128, r: int = 8, p: int = 1, dklen: int = 16) -> str:
    raw = hashlib.scrypt(password=input_str.encode(), salt=salt.encode(), n=n, r=r, p=p, dklen=dklen)
    return binascii.hexlify(raw).decode()


def compute_scrypt_nonce(
    challenge: str,
    salt: str,
    difficulty: int,
    n: int = 128,
    r: int = 8,
    p: int = 1,
    dklen: int = 16,
    **kwargs,
) -> Optional[str]:
    prefix = challenge + salt
    for nonce in itertools.count():
        candidate = scrypt_func(prefix + str(nonce), salt, n, r, p, dklen)
        digest = bytes.fromhex(candidate)
        if _check(digest, difficulty):
            return str(nonce)
    return None


_DEFAULT_BANDWIDTH_SIZES = {
    1: 0x400,
    2: 0xA * 0x400,
    3: 0x64 * 0x400,
    4: 0x100000,
    5: 0xA * 0x100000,
}


def network_bandwidth(challenge: str, salt: str, difficulty: int, **kwargs) -> str:
    """NetworkBandwidth challenge — returns base64-encoded zero buffer sized by difficulty."""
    sizes = kwargs.get("bandwidth_sizes") or _DEFAULT_BANDWIDTH_SIZES
    size = sizes.get(difficulty, 0x400)
    return base64.b64encode(b"\x00" * size).decode()


# Known challenge type hashes → solver functions.
# The challenge.js is also parsed at runtime to discover endpoint names and new types.
CHALLENGE_SOLVERS: dict[str, Callable[..., Any]] = {
    "h72f957df656e80ba55f5d8ce2e8c7ccb59687dba3bfb273d54b08a261b2f3002": compute_scrypt_nonce,
    "h7b0c470f0cfe3a80a9e26526ad185f484f6817d0832712a4a37a908786a6a67f": hash_pow,
    "ha9faaffd31b4d5ede2a2e19d2d7fd525f66fee61911511960dcbb52d3c48ce25": network_bandwidth,
}
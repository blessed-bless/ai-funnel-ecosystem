import hashlib
import hmac
import secrets


def hash_password(password: str, *, iterations: int = 200_000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iterations_s, salt, digest = encoded.split("$", 3)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    iterations = int(iterations_s)
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(candidate, digest)

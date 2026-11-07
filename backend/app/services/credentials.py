"""Encrypt secrets stored in the database (mailbox passwords).

Fernet (AES-128-CBC + HMAC). The key comes from EMAIL_CREDENTIALS_KEY or, for local
development, is generated once into backend/.local/credentials.key (git-ignored, mode 600).
Losing the key only means stored mailbox passwords must be entered again.
"""

import os
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

KEY_FILE = Path(__file__).resolve().parents[2] / ".local" / "credentials.key"


class CredentialsError(RuntimeError):
    pass


@lru_cache
def _fernet() -> Fernet:
    configured = get_settings().email_credentials_key
    if configured is not None:
        key = configured.get_secret_value().encode()
    else:
        if not KEY_FILE.exists():
            KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            KEY_FILE.write_bytes(Fernet.generate_key())
            try:
                os.chmod(KEY_FILE, 0o600)
            except OSError:
                pass
        key = KEY_FILE.read_bytes().strip()
    try:
        return Fernet(key)
    except ValueError as exc:
        raise CredentialsError("EMAIL_CREDENTIALS_KEY is not a valid Fernet key.") from exc


def encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise CredentialsError("Stored password cannot be decrypted (the key changed); reconnect the mailbox.") from exc

from cryptography.fernet import Fernet
import hashlib

from app.utils.config import settings

# Create Fernet instance at module level using settings
_fernet: Fernet | None = None


def get_fernet() -> Fernet:
    """Get or create Fernet instance for encryption/decryption"""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.DB_ENCRYPTION_KEY)
    return _fernet


def encrypt(value: str) -> str:
    """Encrypt a string value"""
    if value is None:
        return None
    return get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt an encrypted string value"""
    if value is None:
        return None
    return get_fernet().decrypt(value.encode()).decode()


def hash_username(value: str) -> str:
    """Hash a username for lookup"""
    if value is None:
        return None
    return hashlib.sha256(value.encode()).hexdigest()

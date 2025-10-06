from flask import current_app
from cryptography.fernet import Fernet
import hashlib

def get_fernet():
    DB_ENCRYPTION_KEY = current_app.config["DB_ENCRYPTION_KEY"]
    if DB_ENCRYPTION_KEY:
        fernet = Fernet(DB_ENCRYPTION_KEY)
    else:
        fernet = Fernet.generate_key()
    return fernet

def encrypt(value: str) -> str:
    if value is None:
        return None
    return get_fernet().encrypt(value.encode()).decode()

def decrypt(value: str) -> str:
    if value is None:
        return None
    return get_fernet().decrypt(value.encode()).decode()

def hash_username(value: str) -> str:
    if value is None:
        return None
    return hashlib.sha256(value.encode()).hexdigest()

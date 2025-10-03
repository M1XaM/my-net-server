# import app
from flask import current_app
import hashlib
from cryptography.fernet import Fernet

def get_fernet():
    APP_ENCRYPTION_KEY = current_app.config["APP_ENCRYPTION_KEY"]
    if APP_ENCRYPTION_KEY:
        fernet = Fernet(APP_ENCRYPTION_KEY)
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

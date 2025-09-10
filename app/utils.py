import time, os
from app import db
from sqlalchemy.exc import OperationalError
from cryptography.fernet import Fernet


def init_db(app):
    retries = 10
    while retries > 0:
        try:
            with app.app_context():
                db.create_all()
            print("✅ Database initialized successfully!")
            break
        except OperationalError as e:
            print(f"⏳ DB not ready ({e}), retrying in 5s...")
            retries -= 1
            time.sleep(5)
    else:
        raise Exception("❌ Could not connect to DB")
    
ENCRYPTION_KEY = os.getenv("APP_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # In dev, auto-generate one so things still work
    ENCRYPTION_KEY = Fernet.generate_key()
    print("⚠️ No APP_ENCRYPTION_KEY set, using a temporary one (dev only).")

fernet = Fernet(ENCRYPTION_KEY)

def encrypt(value: str) -> str:
    """Encrypts a string, returns ciphertext as str."""
    if value is None:
        return None
    return fernet.encrypt(value.encode()).decode()

def decrypt(value: str) -> str:
    """Decrypts a string, returns plaintext."""
    if value is None:
        return None
    return fernet.decrypt(value.encode()).decode()
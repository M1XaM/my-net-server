import os
from dotenv import load_dotenv

# Load .env (but env vars already set take priority)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

class Config:
    DB_USER = os.getenv('DB_USER', 'chat_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'chat_password')
    DB_HOST = os.getenv('DB_HOST', 'db')
    DB_NAME = os.getenv('DB_NAME', 'chatdb')
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}?sslmode=require'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DB_ENCRYPTION_KEY = os.getenv('DB_ENCRYPTION_KEY', 'some-random-fallback-key-65A8773')

    OAUTH_GOOGLE_CLIENT_ID = os.getenv("OAUTH_GOOGLE_CLIENT_ID", "default_client_id")
    OAUTH_GOOGLE_CLIENT_SECRET = os.getenv("OAUTH_GOOGLE_CLIENT_SECRET", "default_secret")
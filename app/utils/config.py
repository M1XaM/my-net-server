import os
from dotenv import load_dotenv

# Load .env (but env vars already set take priority)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

class Config:
    DB_USER = os.getenv("DB_USER", "chat_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "chat_password")
    DB_HOST = os.getenv("DB_HOST", "db")
    DB_HOST_STANDBY = os.getenv("DB_HOST_STANDBY", "db-standby")

    DB_NAME = os.getenv("DB_NAME", "chatdb")
    SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}?sslmode=require"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    DB_ENCRYPTION_KEY = os.getenv("DB_ENCRYPTION_KEY", "some-random-fallback-key-65A8773")

    OAUTH_GOOGLE_CLIENT_ID = os.getenv("OAUTH_GOOGLE_CLIENT_ID", "default_client_id")
    OAUTH_GOOGLE_CLIENT_SECRET = os.getenv("OAUTH_GOOGLE_CLIENT_SECRET", "default_secret")

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "52")
    
    # SMTP Configuration for email verification
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@mynet.com")
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "MyNet")
    APP_URL = os.getenv("APP_URL", "http://localhost:3000")
    
    @staticmethod
    def make_uri(host):
        return f"postgresql://{Config.DB_USER}:{Config.DB_PASSWORD}@{host}/{Config.DB_NAME}?sslmode=require"


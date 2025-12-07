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

    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os. getenv("MAIL_PORT", 587))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "artem4iknagibator@gmail.com")
    MAIL_PASSWORD = os. getenv("MAIL_PASSWORD", "yohv agsn unct rapr")
    MAIL_FROM_EMAIL = os.getenv("MAIL_FROM_EMAIL", "MyNet")
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "MyNet")


    @staticmethod
    def make_uri(host):
        return f"postgresql://{Config.DB_USER}:{Config.DB_PASSWORD}@{host}/{Config.DB_NAME}?sslmode=require"


import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from functools import lru_cache

# Load .env (but env vars already set take priority)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))


class Settings(BaseSettings):
    # Database settings
    DB_USER: str = os.getenv("DB_USER", "chat_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "chat_password")
    DB_HOST: str = os.getenv("DB_HOST", "db")
    DB_HOST_STANDBY: str = os.getenv("DB_HOST_STANDBY", "db-standby")
    DB_NAME: str = os.getenv("DB_NAME", "chatdb")
    
    # Encryption
    DB_ENCRYPTION_KEY: str = os.getenv("DB_ENCRYPTION_KEY", "some-random-fallback-key-65A8773")
    
    # OAuth
    OAUTH_GOOGLE_CLIENT_ID: str = os.getenv("OAUTH_GOOGLE_CLIENT_ID", "default_client_id")
    OAUTH_GOOGLE_CLIENT_SECRET: str = os.getenv("OAUTH_GOOGLE_CLIENT_SECRET", "default_secret")
    
    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "52")
    
    # Email settings
    MAIL_SERVER: str = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT: int = int(os.getenv("MAIL_PORT", 587))
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM_EMAIL: str = os.getenv("MAIL_FROM_EMAIL", "MyNet")
    MAIL_FROM_NAME: str = os.getenv("MAIL_FROM_NAME", "MyNet")
    
    # CORS
    CORS_ALLOWED_ORIGINS: str = os.getenv("CORS_ALLOWED_ORIGINS", "")
    
    @property
    def origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(',') if o.strip()]
        origins.append("https://localhost:5173")
        return origins
    
    def make_async_uri(self, host: str) -> str:
        """Create async PostgreSQL URI for asyncpg"""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{host}/{self.DB_NAME}?ssl=require"
    
    def make_sync_uri(self, host: str) -> str:
        """Create sync PostgreSQL URI for checking availability"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{host}/{self.DB_NAME}?sslmode=require"
    
    @property
    def MAIN_DB_URI(self) -> str:
        return self.make_async_uri(self.DB_HOST)
    
    @property
    def STANDBY_DB_URI(self) -> str:
        return self.make_async_uri(self.DB_HOST_STANDBY)
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    OAUTH_GOOGLE_CLIENT_SECRET: str
    OAUTH_GOOGLE_CLIENT_ID: str

    model_config = SettingsConfigDict(env_file=os.path.join(os.path.dirname(__file__), ".env"))


settings = Settings()
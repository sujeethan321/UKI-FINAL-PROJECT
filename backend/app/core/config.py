
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DATABASE: str
    JWT_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REMINDER_COOLDOWN_SECONDS: int = Field(default=86400, ge=0, le=31536000)

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

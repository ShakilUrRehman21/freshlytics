import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
# Project-root .env first, then backend/.env (if any) for local overrides
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / "backend" / ".env", override=True)

LOCAL_HOSTS = {"localhost", "127.0.0.1", "db", "postgres", "host.docker.internal"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    PROJECT_NAME: str = "Freshlytics API"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = "supersecretkey_please_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Either set DATABASE_URL directly (e.g. sqlite+aiosqlite:///./freshlytics.db)
    # or the individual POSTGRES_* values.
    DATABASE_URL: Optional[str] = None
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "freshlytics"
    # "auto" → SSL for any non-local host (required by Neon, Supabase, RDS…)
    POSTGRES_SSL: str = "auto"

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173"

    MAX_UPLOAD_MB: int = 8

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://"):]
            if url.startswith("postgresql://"):
                url = "postgresql+asyncpg://" + url[len("postgresql://"):]
            # asyncpg doesn't understand libpq query params like sslmode/channel_binding
            if url.startswith("postgresql+asyncpg://") and "?" in url:
                url = url.split("?", 1)[0]
            return url
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def is_postgres(self) -> bool:
        return self.SQLALCHEMY_DATABASE_URI.startswith("postgresql")

    @property
    def use_ssl(self) -> bool:
        mode = self.POSTGRES_SSL.lower()
        if mode in ("true", "1", "require", "yes"):
            return True
        if mode in ("false", "0", "disable", "no"):
            return False
        if self.DATABASE_URL:
            raw = os.getenv("DATABASE_URL", "")
            if "sslmode=require" in raw:
                return True
            host = self.SQLALCHEMY_DATABASE_URI.split("@")[-1].split("/")[0].split(":")[0]
        else:
            host = self.POSTGRES_SERVER
        return host not in LOCAL_HOSTS

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()

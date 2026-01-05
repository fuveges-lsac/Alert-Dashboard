from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    SECRET_KEY: str = "change-me"
    ALLOWED_ORIGINS: List[str] = ["*"]
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/alert_intelligence"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    REDIS_URL: str = "redis://localhost:6379/0"
    ANTHROPIC_API_KEY: Optional[str] = None
    AZURE_AD_TENANT_ID: Optional[str] = None
    AZURE_AD_CLIENT_ID: Optional[str] = None
    AZURE_AD_CLIENT_SECRET: Optional[str] = None
    AZURE_AD_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # SMTP Email Settings
    SMTP_SERVER: str = "mail.smtp2go.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "LSAC_Site_Checks@outlook.com"
    ALERT_NOTIFY_EMAILS: str = ""  # Comma-separated list of recipients

    @property
    def alert_notify_email_list(self) -> List[str]:
        """Parse comma-separated email list."""
        if not self.ALERT_NOTIFY_EMAILS:
            return []
        return [e.strip() for e in self.ALERT_NOTIFY_EMAILS.split(",") if e.strip()]

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

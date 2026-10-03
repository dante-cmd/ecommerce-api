from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # App
    app_name: str = "E-commerce API"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    frontend_url: str = "http://localhost:3000"

    # Database
    database_url: PostgresDsn
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "ecommerce"

    # Redis
    redis_url: RedisDsn
    celery_broker_url: RedisDsn
    celery_result_backend: RedisDsn

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Mail
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = "noreply@example.com"
    mail_port: int = 587
    mail_server: str = "smtp.example.com"
    mail_starttls: bool = True
    mail_ssl_tls: bool = False

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""

    # Storage
    minio_endpoint: str = "minio:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket_name: str = "ecommerce-media"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_use_ssl: bool = False

    # Observability
    sentry_dsn: str = ""
    enable_prometheus: bool = True

    # Seed
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "Admin123!"

    @property
    def sync_database_url(self) -> str:
        """Alembic/seed require a synchronous driver."""
        url = str(self.database_url)
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        if not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

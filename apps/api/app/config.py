"""
Jewel AI API — Configuration via Pydantic Settings.

Loads from environment variables / .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://jewel:jewel_dev_password@localhost:5432/jewel_ai"

    # ── S3 / MinIO ──────────────────────────────────────────
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin123"
    s3_raw_bucket: str = "jewel-raw-uploads"
    s3_processed_bucket: str = "jewel-processed"
    s3_region: str = "us-east-1"

    # ── Inngest ─────────────────────────────────────────────
    inngest_event_key: str = "local-dev-key"
    inngest_signing_key: str = ""
    inngest_dev: bool = True

    # ── Redis ───────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── API ─────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # ── Auth ────────────────────────────────────────────────
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()

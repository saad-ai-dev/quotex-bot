"""
Application configuration via Pydantic Settings.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables / .env file.

    ALERT-ONLY: This system monitors and scores signals.
    It never places, modifies, or cancels trades.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- MongoDB --
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "quotex_monitoring"

    # -- CORS --
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000", "*"]

    # -- Optional API key authentication --
    API_KEY: Optional[str] = None

    # -- Scheduler intervals --
    EVALUATION_CHECK_INTERVAL_SECONDS: int = 10
    METRICS_REFRESH_INTERVAL_SECONDS: int = 60

    # -- Static file serving (dashboard HTML, sound files) --
    STATIC_DIR: str = "static"

    # -- Application metadata --
    APP_NAME: str = "Quotex Alert Monitoring Dashboard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False


# Singleton instance
settings = Settings()

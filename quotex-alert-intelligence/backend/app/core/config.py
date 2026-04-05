from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "quotex_alerts"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
    ]

    # Alert parsing
    DEFAULT_CONFIDENCE_THRESHOLD: float = 65.0
    PARSE_INTERVAL_MS: int = 2000

    # Evaluation scheduler
    EVALUATION_CHECK_INTERVAL_SECONDS: int = 10

    # API key (optional)
    API_KEY: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()

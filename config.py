import os
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    """
    Centralized configuration management for the AI Media OS.
    Fails fast on startup if required variables are missing or misconfigured.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Core Environment
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # AI Engine — Groq (free tier: 14,400 req/day)
    GROQ_API_KEY: SecretStr = Field(..., description="API key for Groq (get free at console.groq.com)")
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile", description="Groq model to use")

    # Media Retrieval
    PEXELS_API_KEY: SecretStr = Field(..., description="API key for Pexels")
    MAX_CONCURRENT_FETCHES: int = Field(default=5, ge=1, le=20, description="Max concurrent async requests to Pexels")
    MEDIA_TIMEOUT_SECONDS: int = Field(default=15, ge=5, description="Timeout for external API calls")
    ASSETS_DIR: str = Field(default="assets", description="Local directory for storing raw and rendered media")

    # Database
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///data/neuroflux.db", description="Database connection URL")

    # Publishing (Instagram)
    INSTAGRAM_USERNAME: str = Field(default="", description="Instagram account username")
    INSTAGRAM_PASSWORD: SecretStr = Field(default=SecretStr(""), description="Instagram account password")
    # Residential proxy URL — REQUIRED for cloud-hosted deployments to avoid IP bans.
    # Format: http://username:password@proxy-host:port
    # Leave empty to run without a proxy (local dev only).
    INSTAGRAM_PROXY: SecretStr = Field(default=SecretStr(""), description="Residential proxy URL for Instagram requests")

    # Scheduling
    SCHEDULE_INTERVAL_SECONDS: int = Field(default=3600, ge=60, description="Interval between pipeline runs")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

# Instantiate centrally to be imported by other modules.
# Raises ValidationError immediately if .env is improperly configured.
settings = AppConfig()

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str
    API_V1_STR: str
    DATABASE_URL: str
    OPENAI_API_KEY: str | None = None
    ALPHA_VANTAGE_API_KEY: str | None = None
    FRED_API_KEY: str | None = None
    ECOS_API_KEY: str | None = None
    FMP_API_KEY: str | None = None
    FINNHUB_API_KEY: str | None = None
    GOOGLE_CLIENT_ID: str | None = None
    
    # JWT Authentication
    SECRET_KEY: str = "a_very_secure_randomly_generated_string_like_9b0d2a8"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Runtime tasks
    ENABLE_MARKET_WARMUP: bool = True
    ENABLE_SCHEDULER: bool = True
    REPORT_SCHEDULER_COVERAGE: str = "conservative"
    REPORT_SCHEDULER_MAX_REPORTS_PER_RUN: int = 20
    REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS: int = 24
    ENABLE_LLM_REPORT_CRITICS: bool = False
    REPORT_CRITIC_MODE: str = "deterministic"

    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV_FILE),
        extra="ignore",
    )

settings = Settings()

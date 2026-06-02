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

    # Deployment/runtime environment
    ENVIRONMENT: str = "development"
    BACKEND_CORS_ORIGINS: str = ""
    BACKEND_CORS_ORIGIN_REGEX: str | None = None
    LOCAL_CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    ENABLE_DB_SCHEMA_BOOTSTRAP: bool = True
    SQLALCHEMY_ECHO: bool = False
    DB_POOL_PRE_PING: bool = True
    DB_PREPARED_STATEMENT_CACHE_SIZE: int | None = None
    
    # JWT Authentication
    SECRET_KEY: str = "a_very_secure_randomly_generated_string_like_9b0d2a8"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Runtime tasks
    ENABLE_MARKET_WARMUP: bool = True
    ENABLE_SCHEDULER: bool = True
    REPORT_SCHEDULER_COVERAGE: str = "conservative"
    REPORT_SCHEDULER_INTERVAL_HOURS: int = 6
    REPORT_SCHEDULER_MAX_REPORTS_PER_RUN: int = 5
    REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS: int = 6
    REPORT_SCHEDULER_TARGET_TICKERS: str = "DGS10,XAU,BTC-USD,NVDA,005930.KS"
    ENABLE_LLM_REPORT_CRITICS: bool = False
    REPORT_CRITIC_MODE: str = "deterministic"

    # Payment provider boundary. Secret values must be supplied through env.
    PAYMENT_PROVIDER: str | None = None
    PAYMENT_WEBHOOK_SECRET: str | None = None
    PAYMENT_PLUS_PLAN_ID: str | None = None
    PAYMENT_PRO_PLAN_ID: str | None = None
    PAYMENT_MOCK_CHECKOUT_BASE_URL: str | None = None

    # Favorite asset notification boundary. Provider secrets must stay in env only.
    ENABLE_NOTIFICATION_SCHEDULER: bool = False
    NOTIFICATION_EVALUATION_INTERVAL_MINUTES: int = 10
    NOTIFICATION_DELIVERY_INTERVAL_MINUTES: int = 1
    NOTIFICATION_DEFAULT_PRICE_THRESHOLD_PERCENT: float = 3
    NOTIFICATION_DEFAULT_COOLDOWN_MINUTES: int = 180
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_WEBHOOK_SECRET: str | None = None
    EMAIL_PROVIDER: str | None = None
    EMAIL_FROM_ADDRESS: str | None = None
    GMAIL_CLIENT_ID: str | None = None
    GMAIL_CLIENT_SECRET: str | None = None
    GMAIL_REFRESH_TOKEN: str | None = None
    EMAIL_SMTP_HOST: str | None = None
    EMAIL_SMTP_PORT: int = 587
    EMAIL_SMTP_USERNAME: str | None = None
    EMAIL_SMTP_PASSWORD: str | None = None
    EMAIL_SMTP_USE_TLS: bool = True

    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV_FILE),
        extra="ignore",
    )

    def cors_origins(self) -> list[str]:
        origins: list[str] = []
        for raw_origins in (self.LOCAL_CORS_ORIGINS, self.BACKEND_CORS_ORIGINS):
            origins.extend(
                origin.strip().rstrip("/")
                for origin in raw_origins.split(",")
                if origin.strip()
            )
        return list(dict.fromkeys(origins))

settings = Settings()

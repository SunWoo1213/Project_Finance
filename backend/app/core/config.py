from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
ALLOWED_DATABASE_URL_SCHEMES = {"postgresql+asyncpg", "sqlite+aiosqlite"}
POSTGRES_FALLBACK_ENV_NAMES = ("POSTGRES_URL_NON_POOLING", "POSTGRES_URL")
POSTGRES_SSLMODES_REQUIRING_SSL = {"allow", "prefer", "require", "verify-ca", "verify-full"}


def normalize_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        value = "postgresql+asyncpg://" + value[len("postgres://"):]
    elif value.startswith("postgresql://"):
        value = "postgresql+asyncpg://" + value[len("postgresql://"):]

    parsed = urlparse(value)
    if parsed.scheme != "postgresql+asyncpg":
        return value

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    normalized_query_pairs: list[tuple[str, str]] = []
    sslmode_value: str | None = None
    for key, query_value in query_pairs:
        if key == "sslmode":
            sslmode_value = query_value
            continue
        normalized_query_pairs.append((key, query_value))

    if sslmode_value in POSTGRES_SSLMODES_REQUIRING_SSL and not any(
        key == "ssl" for key, _ in normalized_query_pairs
    ):
        normalized_query_pairs.append(("ssl", sslmode_value))

    return urlunparse(parsed._replace(query=urlencode(normalized_query_pairs)))


def build_asyncpg_connect_args(
    database_url: str,
    prepared_statement_cache_size: int | None,
) -> dict[str, int]:
    connect_args: dict[str, int] = {}
    if prepared_statement_cache_size is not None:
        connect_args["prepared_statement_cache_size"] = prepared_statement_cache_size
    return connect_args


class Settings(BaseSettings):
    _database_url_source: str = PrivateAttr(default="DATABASE_URL")

    PROJECT_NAME: str
    API_V1_STR: str
    DATABASE_URL: str | None = None
    POSTGRES_URL: str | None = None
    POSTGRES_URL_NON_POOLING: str | None = None
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
    ENABLE_AI_REPORT_GENERATION: bool = True
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

    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV_FILE),
        extra="ignore",
    )

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        database_url_source = "DATABASE_URL"
        if not self.DATABASE_URL:
            for env_name in POSTGRES_FALLBACK_ENV_NAMES:
                candidate = getattr(self, env_name)
                if candidate:
                    self.DATABASE_URL = candidate
                    database_url_source = env_name
                    break

        if not self.DATABASE_URL:
            fallback_names = ", ".join(POSTGRES_FALLBACK_ENV_NAMES)
            raise ValueError(
                "DATABASE_URL is required. For Vercel/Supabase environments, "
                f"the backend can also derive it from one of: {fallback_names}."
            )

        self.DATABASE_URL = normalize_database_url(self.DATABASE_URL)
        self._database_url_source = database_url_source
        parsed = urlparse(self.DATABASE_URL)
        if parsed.scheme not in ALLOWED_DATABASE_URL_SCHEMES:
            allowed = ", ".join(sorted(ALLOWED_DATABASE_URL_SCHEMES))
            raise ValueError(
                "DATABASE_URL must use an async SQLAlchemy driver scheme. "
                f"Allowed schemes after normalization: {allowed}."
            )
        if parsed.scheme == "postgresql+asyncpg" and not parsed.hostname:
            raise ValueError("DATABASE_URL with postgresql+asyncpg must include a host.")
        if parsed.scheme == "postgresql+asyncpg":
            authority = parsed.netloc.rsplit("@", 1)[-1]
            if authority.endswith(":"):
                raise ValueError("DATABASE_URL contains an invalid port.")
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("DATABASE_URL contains an invalid port.") from exc
        return self

    @field_validator("DB_PREPARED_STATEMENT_CACHE_SIZE", mode="before")
    @classmethod
    def empty_optional_int_as_none(cls, value: str | int | None) -> str | int | None:
        if value == "":
            return None
        return value

    def cors_origins(self) -> list[str]:
        origins: list[str] = []
        for raw_origins in (self.LOCAL_CORS_ORIGINS, self.BACKEND_CORS_ORIGINS):
            origins.extend(
                origin.strip().rstrip("/")
                for origin in raw_origins.split(",")
                if origin.strip()
            )
        return list(dict.fromkeys(origins))

    def database_connect_args(self) -> dict[str, int]:
        return build_asyncpg_connect_args(
            self.DATABASE_URL,
            self.DB_PREPARED_STATEMENT_CACHE_SIZE,
        )

    def database_url_diagnostics(self) -> dict[str, str | int | None]:
        parsed = urlparse(self.DATABASE_URL)
        port = None
        try:
            port = parsed.port
        except ValueError:
            port = None
        return {
            "source": self._database_url_source,
            "scheme": parsed.scheme,
            "host": parsed.hostname if parsed.scheme != "sqlite+aiosqlite" else None,
            "port": port,
        }

settings = Settings()

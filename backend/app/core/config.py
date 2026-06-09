from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
ALLOWED_DATABASE_URL_SCHEMES = {"postgresql+asyncpg", "sqlite+aiosqlite"}
POSTGRES_FALLBACK_ENV_NAMES = ("POSTGRES_URL_NON_POOLING", "POSTGRES_URL")
POSTGRES_SSLMODES_REQUIRING_SSL = {"allow", "prefer", "require", "verify-ca", "verify-full"}


def normalize_database_url(value: str) -> str:
    value = value.strip()
    # Hosting dashboards (e.g. Render) sometimes store the value with literal
    # surrounding quotes; strip a single matching pair so scheme detection works.
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()
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
    COINGECKO_DEMO_API_KEY: str | None = None
    DATA_GO_KR_API_KEY: str | None = None
    STOOQ_API_KEY: str | None = None
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

    # Market data refresh cadence (excludes AI reports). All values in minutes.
    MARKET_PRICES_REFRESH_MINUTES: int = 5
    MARKET_NEWS_REFRESH_MINUTES: int = 60
    MARKET_LATEST_CONTEXT_TTL_MINUTES: int = 10
    MARKET_LIVE_TICKERS: str = "DGS10,XAU,BTC-USD,NVDA,005930.KS,^GSPC,^NDX,KRW=X,^KS11"

    # Per-asset fetch timeout for warm-up/scheduler collection (seconds).
    # Higher values let a serialized provider queue drain within one run. The KR
    # stock snapshot path makes two data.go.kr calls (~20s each), so this must be
    # comfortably above 2 * DATA_GO_KR_FETCH_TIMEOUT_SECONDS or even an
    # uncontended KR asset cannot finish before the per-asset timeout fires.
    MARKET_PRICE_FETCH_TIMEOUT_SECONDS: int = 55
    MARKET_NEWS_FETCH_TIMEOUT_SECONDS: int = 20

    # data.go.kr (KR stock/index) calls can spike to ~20s. Give them a longer
    # internal timeout and a small concurrency bump so the serialized queue can
    # drain across scheduler cycles. Concurrency is deliberately conservative:
    # data.go.kr rate-limits aggressively and returns a gateway block page
    # ("허용되지 않는 요청") under load, so default to 2 and only raise via env if
    # the deployment tolerates it (see AGENTS.md section 9).
    DATA_GO_KR_FETCH_TIMEOUT_SECONDS: int = 25
    DATA_GO_KR_MAX_CONCURRENCY: int = 2
    FMP_FETCH_TIMEOUT_SECONDS: int = 10
    FMP_DAILY_CALL_BUDGET: int = 180
    ENABLE_STOOQ_FALLBACK: bool = False
    STOOQ_FETCH_TIMEOUT_SECONDS: int = 12

    ENABLE_AI_REPORT_GENERATION: bool = True
    REPORT_SCHEDULER_COVERAGE: str = "conservative"
    REPORT_SCHEDULER_INTERVAL_HOURS: int = 6
    # 기동 후 첫 리포트 생성까지 지연(초). interval 잡의 next_run_time으로 사용된다.
    # sleep/재시작형 런타임에서 인스턴스가 일찍 죽어도 첫 발화를 놓치지 않도록 짧게 둔다
    # (warm-up은 비차단이고, generate_report_for_ticker가 per-ticker 캐시 fill로 보강).
    REPORT_SCHEDULER_STARTUP_DELAY_SECONDS: int = 60
    REPORT_SCHEDULER_MAX_REPORTS_PER_RUN: int = 5
    REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS: int = 6
    REPORT_SCHEDULER_TARGET_TICKERS: str = "DGS10,XAU,BTC-USD,NVDA,005930.KS"
    ENABLE_LLM_REPORT_CRITICS: bool = False
    REPORT_CRITIC_MODE: str = "deterministic"
    # 품질 게이트(포맷/숫자/정성/평가) 실패 시 writer 재작성 최대 횟수.
    # 이 값에 도달하면 그래프가 END로 빠진다(이후 숫자 정제 폴백 저장 시도).
    # 값이 클수록 통과율은 오르지만 실패 리포트당 LLM 호출이 늘어 비용이 증가한다.
    REPORT_MAX_REVISIONS: int = 7

    # Chatbot LLM intent understanding. Default off so the rule-based path stays
    # the safe baseline and no OpenAI cost is incurred unless explicitly enabled.
    # The LLM path is tool-grounded and must never generate AI reports; it only
    # reads stored scheduled reports (see AGENTS.md section 14).
    ENABLE_LLM_CHATBOT: bool = False
    CHATBOT_LLM_MODEL: str = "gpt-4o-mini"
    CHATBOT_HISTORY_MAX_TURNS: int = 10
    CHATBOT_LLM_TIMEOUT_SECONDS: int = 20
    # When on, the LLM answer's price/percent numbers are checked against the
    # assembled grounding; unverified figures get a caveat and lower confidence.
    CHATBOT_GROUNDING_GUARD: bool = True

    # Payment provider boundary. Secret values must be supplied through env.
    PAYMENT_PROVIDER: str | None = None
    PAYMENT_WEBHOOK_SECRET: str | None = None
    PAYMENT_PLUS_PLAN_ID: str | None = None
    PAYMENT_PRO_PLAN_ID: str | None = None
    PAYMENT_MOCK_CHECKOUT_BASE_URL: str | None = None
    TOSS_API_BASE_URL: str = "https://api.tosspayments.com"
    TOSS_CLIENT_KEY: str | None = None
    TOSS_SECRET_KEY: str | None = None
    TOSS_PLUS_AMOUNT_KRW: int = 1000
    TOSS_PRO_AMOUNT_KRW: int = 3000
    TOSS_BILLING_SUCCESS_URL: str | None = None
    TOSS_BILLING_FAIL_URL: str | None = None
    ENABLE_BILLING_SCHEDULER: bool = False
    BILLING_RENEWAL_INTERVAL_MINUTES: int = 60
    BILLING_RETRY_LIMIT: int = 3
    BILLING_RETRY_BACKOFF_HOURS: int = 24

    # Favorite asset notification boundary. Provider secrets must stay in env only.
    ENABLE_NOTIFICATION_SCHEDULER: bool = False
    NOTIFICATION_EVALUATION_INTERVAL_MINUTES: int = 10
    NOTIFICATION_DELIVERY_INTERVAL_MINUTES: int = 1
    NOTIFICATION_DEFAULT_PRICE_THRESHOLD_PERCENT: float = 3
    NOTIFICATION_DEFAULT_COOLDOWN_MINUTES: int = 180
    FRONTEND_BASE_URL: str = "http://localhost:5173"
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
            detected = parsed.scheme or "(none)"
            raise ValueError(
                "DATABASE_URL must use an async SQLAlchemy driver scheme. "
                f"Allowed schemes after normalization: {allowed}. "
                f"Detected scheme: {detected}. "
                "Ensure the value starts with postgresql:// or postgres:// "
                "(the DB connection string, not the https:// API URL) and has no "
                "surrounding quotes."
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

    @field_validator(
        "MARKET_PRICES_REFRESH_MINUTES",
        "MARKET_NEWS_REFRESH_MINUTES",
        "MARKET_LATEST_CONTEXT_TTL_MINUTES",
    )
    @classmethod
    def enforce_minimum_minutes(cls, value: int) -> int:
        # Guard against 0/negative cadence which would break the scheduler
        # interval jobs and the latest-context freshness window.
        return max(1, int(value))

    @field_validator(
        "MARKET_PRICE_FETCH_TIMEOUT_SECONDS",
        "MARKET_NEWS_FETCH_TIMEOUT_SECONDS",
        "DATA_GO_KR_FETCH_TIMEOUT_SECONDS",
        "FMP_FETCH_TIMEOUT_SECONDS",
        "STOOQ_FETCH_TIMEOUT_SECONDS",
    )
    @classmethod
    def enforce_minimum_fetch_timeout(cls, value: int) -> int:
        # Guard against a too-short timeout that would mass-fail assets while a
        # serialized provider queue is still draining.
        return max(5, int(value))

    @field_validator("FMP_DAILY_CALL_BUDGET")
    @classmethod
    def enforce_non_negative_fmp_budget(cls, value: int) -> int:
        return max(0, int(value))

    @field_validator("TOSS_PLUS_AMOUNT_KRW", "TOSS_PRO_AMOUNT_KRW")
    @classmethod
    def enforce_non_negative_payment_amount(cls, value: int) -> int:
        return max(0, int(value))

    @field_validator("BILLING_RENEWAL_INTERVAL_MINUTES", "BILLING_RETRY_BACKOFF_HOURS")
    @classmethod
    def enforce_minimum_billing_interval(cls, value: int) -> int:
        return max(1, int(value))

    @field_validator("BILLING_RETRY_LIMIT")
    @classmethod
    def enforce_non_negative_retry_limit(cls, value: int) -> int:
        return max(0, int(value))

    @field_validator("REPORT_SCHEDULER_STARTUP_DELAY_SECONDS")
    @classmethod
    def enforce_non_negative_startup_delay(cls, value: int) -> int:
        return max(0, int(value))

    @field_validator("DATA_GO_KR_MAX_CONCURRENCY")
    @classmethod
    def enforce_minimum_concurrency(cls, value: int) -> int:
        # At least one in-flight call; 0/negative would deadlock the provider.
        return max(1, int(value))

    @field_validator("FRONTEND_BASE_URL")
    @classmethod
    def normalize_frontend_base_url(cls, value: str) -> str:
        return (value or "http://localhost:5173").strip().rstrip("/")

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

import asyncio
from contextlib import asynccontextmanager
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .core.cache import market_cache
from .core.config import settings
from .core.log_sanitizer import redact_secrets
from .db.session import engine, get_db
from .models import AIReport, Asset, Base
from .services.ai_service import (
    generate_daily_reports,
)
from .services.market_service import fetch_latest_asset_context, update_news_task, update_prices_task
from .services.notification_service import evaluate_notifications, send_pending_notifications
from .services.price_providers import fetch_market_history
try:
    from app.services.macro_service import (
        fetch_kr_bond_data,
        fetch_kr_bond_history,
        fetch_us_bond_data,
        fetch_us_bond_history,
    )
except ModuleNotFoundError:
    from .services.macro_service import (
        fetch_kr_bond_data,
        fetch_kr_bond_history,
        fetch_us_bond_data,
        fetch_us_bond_history,
    )
from .api import auth, billing, chat, community, favorites, notifications, profile
from .models import User
from .api.deps import get_current_user, require_report_access

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
# 외부 호출 URL(쿼리스트링의 API 키 포함)과 SQL echo가 INFO 로그로 평문 노출되지
# 않도록 민감/노이즈 로거 레벨을 WARNING으로 낮춘다. 오류 추적(WARNING 이상)은 유지된다.
for _noisy_logger in ("httpx", "httpcore", "sqlalchemy.engine"):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

REQUIRED_TABLES = {
    "users",
    "assets",
    "ai_reports",
    "comments",
    "comment_likes",
    "comment_reports",
    "subscriptions",
    "billing_events",
    "user_favorite_assets",
    "notification_preferences",
    "notification_channel_connections",
    "notification_rules",
    "asset_notification_snapshots",
    "notification_events",
}

REQUIRED_AI_REPORT_COLUMNS = {
    "quality_status",
    "quality_feedback",
    "format_check_pass",
    "fact_check_pass",
    "qualitative_check_pass",
    "revision_count",
    "data_as_of",
    "source_summary",
    "risk_summary",
    "analysis_framework",
    "metadata_json",
}

REQUIRED_USER_COLUMNS = {
    "nickname_confirmed_at",
}


async def ensure_ai_report_metadata_columns(conn) -> None:
    statements = [
        "ALTER TABLE ai_reports ADD COLUMN IF NOT EXISTS quality_status VARCHAR",
        "ALTER TABLE ai_reports ADD COLUMN IF NOT EXISTS quality_feedback TEXT",
        "ALTER TABLE ai_reports ADD COLUMN IF NOT EXISTS format_check_pass BOOLEAN",
        "ALTER TABLE ai_reports ADD COLUMN IF NOT EXISTS fact_check_pass BOOLEAN",
        "ALTER TABLE ai_reports ADD COLUMN IF NOT EXISTS qualitative_check_pass BOOLEAN",
        "ALTER TABLE ai_reports ADD COLUMN IF NOT EXISTS revision_count INTEGER",
        "ALTER TABLE ai_reports ADD COLUMN IF NOT EXISTS data_as_of TIMESTAMP",
        "ALTER TABLE ai_reports ADD COLUMN IF NOT EXISTS source_summary JSON",
        "ALTER TABLE ai_reports ADD COLUMN IF NOT EXISTS risk_summary TEXT",
        "ALTER TABLE ai_reports ADD COLUMN IF NOT EXISTS analysis_framework JSON",
        "ALTER TABLE ai_reports ADD COLUMN IF NOT EXISTS metadata_json JSON",
    ]
    for statement in statements:
        await conn.execute(text(statement))


async def ensure_user_profile_columns(conn) -> None:
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname_confirmed_at TIMESTAMP",
    ]
    for statement in statements:
        await conn.execute(text(statement))


def get_schema_gaps(sync_conn) -> list[str]:
    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())
    missing_tables = sorted(REQUIRED_TABLES - table_names)
    gaps = [f"missing table: {table}" for table in missing_tables]

    if "ai_reports" in table_names:
        ai_report_columns = {column["name"] for column in inspector.get_columns("ai_reports")}
        missing_columns = sorted(REQUIRED_AI_REPORT_COLUMNS - ai_report_columns)
        gaps.extend(f"missing ai_reports column: {column}" for column in missing_columns)

    if "users" in table_names:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        missing_columns = sorted(REQUIRED_USER_COLUMNS - user_columns)
        gaps.extend(f"missing users column: {column}" for column in missing_columns)

    return gaps


async def verify_database_schema(conn) -> None:
    gaps = await conn.run_sync(get_schema_gaps)
    if gaps:
        raise RuntimeError("Database schema is not migration-ready: " + ", ".join(gaps))


async def prepare_database_on_startup() -> None:
    if settings.ENABLE_DB_SCHEMA_BOOTSTRAP:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await ensure_ai_report_metadata_columns(conn)
                await ensure_user_profile_columns(conn)
            logger.info("Database bootstrap completed")
        except Exception:
            logger.warning(
                "Database bootstrap failed and startup continued because "
                "ENABLE_DB_SCHEMA_BOOTSTRAP=true. /health only checks app liveness; "
                "use /db-check for database readiness. database_target=%s",
                settings.database_url_diagnostics(),
            )
        return

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        await verify_database_schema(conn)
    logger.info("Database bootstrap disabled; migration-managed schema check completed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await prepare_database_on_startup()

    warmup_task: asyncio.Task | None = None
    if settings.ENABLE_MARKET_WARMUP:
        async def run_market_warmup() -> None:
            # Run warm-up in the background so the server binds its port and passes
            # health checks immediately; the in-memory cache fills in shortly after.
            print("[lifespan] initial market cache warm-up started")
            try:
                await update_prices_task()
                await update_news_task()
                print("[lifespan] initial market cache warm-up completed")
            except Exception as exc:
                print(f"[lifespan] initial market cache warm-up failed: {exc!r}")

        warmup_task = asyncio.create_task(run_market_warmup())
    else:
        print("[lifespan] initial market cache warm-up skipped")

    scheduler = None
    if settings.ENABLE_SCHEDULER:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            update_prices_task,
            "interval",
            minutes=settings.MARKET_PRICES_REFRESH_MINUTES,
            id="update_prices_task",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            update_news_task,
            "interval",
            minutes=settings.MARKET_NEWS_REFRESH_MINUTES,
            id="update_news_task",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

        if settings.ENABLE_AI_REPORT_GENERATION:
            async def run_daily_reports_job() -> None:
                logger.info("AI 리포트 생성 시작")
                try:
                    await generate_daily_reports()
                    logger.info("AI 리포트 생성 종료")
                except Exception as e:
                    logger.error(f"리포트 생성 중 에러 발생: {e}", exc_info=True)

            scheduler.add_job(
                run_daily_reports_job,
                "interval",
                hours=settings.REPORT_SCHEDULER_INTERVAL_HOURS,
                id="generate_daily_reports",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
            scheduler.add_job(
                run_daily_reports_job,
                "date",
                run_date=datetime.now() + timedelta(seconds=settings.REPORT_SCHEDULER_STARTUP_DELAY_SECONDS),
                id="generate_daily_reports_startup",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
            report_scheduler_status = f"reports: every {settings.REPORT_SCHEDULER_INTERVAL_HOURS} hours"
        else:
            logger.info("AI report generation scheduler skipped because ENABLE_AI_REPORT_GENERATION=false")
            report_scheduler_status = "reports: disabled by ENABLE_AI_REPORT_GENERATION"
        if settings.ENABLE_NOTIFICATION_SCHEDULER:
            async def run_notification_evaluation_job() -> None:
                logger.info("Notification evaluation started")
                async for db in get_db():
                    try:
                        created = await evaluate_notifications(db)
                        sent, failed = await send_pending_notifications(db)
                        logger.info(
                            "Notification evaluation completed (created=%s, sent=%s, failed=%s)",
                            created,
                            sent,
                            failed,
                        )
                    except Exception as exc:
                        logger.error("Notification evaluation failed: %s", exc, exc_info=True)
                    break

            async def run_notification_delivery_job() -> None:
                logger.info("Notification delivery started")
                async for db in get_db():
                    try:
                        sent, failed = await send_pending_notifications(db)
                        logger.info("Notification delivery completed (sent=%s, failed=%s)", sent, failed)
                    except Exception as exc:
                        logger.error("Notification delivery failed: %s", exc, exc_info=True)
                    break

            scheduler.add_job(
                run_notification_evaluation_job,
                "interval",
                minutes=settings.NOTIFICATION_EVALUATION_INTERVAL_MINUTES,
                id="notification_evaluation",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
            scheduler.add_job(
                run_notification_delivery_job,
                "interval",
                minutes=settings.NOTIFICATION_DELIVERY_INTERVAL_MINUTES,
                id="notification_delivery",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
        scheduler.start()
        print(
            "[lifespan] scheduler started "
            f"(prices:{settings.MARKET_PRICES_REFRESH_MINUTES}m, "
            f"news:{settings.MARKET_NEWS_REFRESH_MINUTES}m, {report_scheduler_status})"
        )
    else:
        print("[lifespan] scheduler skipped")

    app.state.scheduler = scheduler
    app.state.warmup_task = warmup_task

    try:
        yield
    finally:
        if warmup_task is not None and not warmup_task.done():
            warmup_task.cancel()
            try:
                await warmup_task
            except (asyncio.CancelledError, Exception):
                pass
        if scheduler is not None:
            scheduler.shutdown(wait=False)
            print("[lifespan] scheduler stopped")


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_origin_regex=settings.BACKEND_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(community.router)
app.include_router(chat.router)
app.include_router(favorites.router)
app.include_router(notifications.router)
app.include_router(profile.router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "project": settings.PROJECT_NAME,
        "database": "not_checked",
        "database_check": "/db-check",
    }


@app.get("/db-check")
async def db_check(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(text("SELECT 1"))
        value = result.scalar()
        if value == 1:
            return {
                "status": "db_connected",
                "database": settings.database_url_diagnostics(),
            }
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Database connectivity check returned an unexpected result.",
                "database": settings.database_url_diagnostics(),
            },
        )
    except HTTPException:
        raise
    except Exception:
        logger.warning(
            "Database connectivity check failed. database_target=%s",
            settings.database_url_diagnostics(),
        )
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Database connectivity check failed.",
                "database": settings.database_url_diagnostics(),
            },
        )


@app.get("/api/market/prices")
async def get_market_prices():
    return market_cache["prices"]


@app.get("/api/market/news")
async def get_market_news():
    return market_cache["news"]


@app.get("/api/market/latest-context/{ticker}")
async def get_latest_market_context(ticker: str, force_refresh: bool = Query(False)):
    return await fetch_latest_asset_context(ticker, force_refresh=force_refresh)


@app.get("/api/market/history/{ticker}")
async def get_market_history(ticker: str, period: str = Query("1y", pattern="^(1d|1mo|1y|5y)$")):
    try:
        period_days_map = {"1d": 7, "1mo": 30, "1y": 365, "5y": 1825}
        asset_ticker = (ticker or "").strip().upper()

        def build_points(history_prices: list[float]) -> list[dict]:
            base_date = datetime.now()
            return [
                {
                    "date": (base_date - timedelta(days=(len(history_prices) - 1 - i))).strftime("%Y-%m-%d"),
                    "value": float(price),
                }
                for i, price in enumerate(history_prices)
            ]

        # Bond providers preserve the existing FRED/ECOS routes.
        if asset_ticker in [
            "KTB_1Y",
            "KTB_3Y",
            "KTB_5Y",
            "KTB_10Y",
            "KTB_20Y",
            "KTB_30Y",
            "0101500",
            "0102000",
        ]:
            points = await fetch_kr_bond_history(asset_ticker, lookback_days=period_days_map.get(period, 365))
            if not points:
                logger.warning(
                    "No KR bond history found (assetTicker=%s, period=%s). "
                    "Use asset ticker (e.g. KTB_1Y/KTB_10Y), not raw ECOS code.",
                    asset_ticker,
                    period,
                )
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"No KR bond history found for assetTicker={asset_ticker}. "
                        "Expected asset ticker such as KTB_1Y or KTB_10Y."
                    ),
                )
            return {
                "ticker": asset_ticker,
                "series_type": "yield",
                "unit": "%",
                "points": points,
                "legacy": [{"date": p["date"], "close": p["value"], "value": p["value"]} for p in points],
            }
        elif asset_ticker in ["DGS10", "DGS30", "DGS1", "DGS3MO", "DGS2MO"]:
            points = await fetch_us_bond_history(asset_ticker, limit=period_days_map.get(period, 365))
            if not points:
                raise HTTPException(status_code=404, detail=f"No US bond history found for ticker: {asset_ticker}")
            return {
                "ticker": asset_ticker,
                "series_type": "yield",
                "unit": "%",
                "points": points,
                "legacy": [{"date": p["date"], "close": p["value"], "value": p["value"]} for p in points],
                "provider_meta": {"provider": "fred", "series_id": asset_ticker, "freshness": "provider_observation"},
            }

        data = await fetch_market_history(asset_ticker, period)
        response = {
            "ticker": data.get("ticker", asset_ticker),
            "series_type": data.get("series_type", "price"),
            "unit": data.get("unit", "USD"),
            "points": data.get("points", []),
            "legacy": data.get("legacy", []),
        }
        if data.get("provider_meta"):
            response["provider_meta"] = data["provider_meta"]
        return response
    except HTTPException:
        raise
    except Exception as e:
        # 외부 데이터 예외(FRED HTTPStatusError 등)에는 URL 쿼리스트링의 API 키가
        # 포함될 수 있어, 응답 detail에 시크릿이 새지 않도록 마스킹한다.
        raise HTTPException(status_code=500, detail=redact_secrets(str(e)))


def ensure_report_generation_allowed(user: User) -> None:
    raise HTTPException(
        status_code=403,
        detail="Manual AI report generation is disabled. Reports are generated by the backend scheduler.",
    )


@app.post("/api/ai/generate/{ticker}")
async def generate_report(
    ticker: str,
    current_user: User = Depends(get_current_user),
):
    ensure_report_generation_allowed(current_user)


def report_metadata_payload(report: AIReport) -> dict:
    metadata = report.metadata_json or {}
    if metadata:
        return metadata
    return {
        "quality_status": report.quality_status,
        "feedback": report.quality_feedback or "",
        "format_check_pass": report.format_check_pass,
        "fact_check_pass": report.fact_check_pass,
        "qualitative_check_pass": report.qualitative_check_pass,
        "revision_count": report.revision_count,
        "data_as_of": report.data_as_of.isoformat() if report.data_as_of else None,
        "source_status": report.source_summary or {},
        "risk_summary": report.risk_summary or "",
        "analysis_framework": report.analysis_framework or {},
    }


@app.get("/api/reports/{ticker}")
async def get_latest_report(
    ticker: str,
    current_user: User = Depends(require_report_access),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(AIReport, Asset)
        .join(Asset, AIReport.asset_id == Asset.id)
        .where(Asset.ticker == ticker)
        .order_by(AIReport.created_at.desc())
        .limit(1)
    )
    result = await db.execute(query)
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No report found for ticker: {ticker}")

    report, asset = row
    return {
        "ticker": asset.ticker,
        "bull_summary": report.bull_summary,
        "bear_summary": report.bear_summary,
        "final_content": report.final_content,
        "created_at": report.created_at.isoformat(),
        "metadata": report_metadata_payload(report),
    }

from contextlib import asynccontextmanager
import logging
from datetime import datetime, timedelta

import yfinance as yf
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .core.cache import market_cache
from .core.config import settings
from .db.session import engine, get_db
from .models import AIReport, Asset, Base
from .services.ai_service import (
    generate_daily_reports,
)
from .services.market_service import fetch_latest_asset_context, update_news_task, update_prices_task
from .services.notification_service import evaluate_notifications, send_pending_notifications
try:
    from app.services.macro_service import (
        fetch_commodity_data,
        fetch_kr_bond_data,
        fetch_kr_bond_history,
        fetch_us_bond_data,
    )
except ModuleNotFoundError:
    from .services.macro_service import (
        fetch_commodity_data,
        fetch_kr_bond_data,
        fetch_kr_bond_history,
        fetch_us_bond_data,
    )
from .api import auth, billing, chat, community, favorites, notifications, profile
from .models import User
from .api.deps import get_current_user, require_report_access

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
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
            logger.warning("Database bootstrap skipped after startup initialization failure")
        return

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        await verify_database_schema(conn)
    logger.info("Database bootstrap disabled; migration-managed schema check completed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await prepare_database_on_startup()

    if settings.ENABLE_MARKET_WARMUP:
        print("[lifespan] initial market cache warm-up started")
        await update_prices_task()
        await update_news_task()
        print("[lifespan] initial market cache warm-up completed")
    else:
        print("[lifespan] initial market cache warm-up skipped")

    scheduler = None
    if settings.ENABLE_SCHEDULER:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            update_prices_task,
            "interval",
            minutes=5,
            id="update_prices_task",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            update_news_task,
            "interval",
            hours=1,
            id="update_news_task",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

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
            run_date=datetime.now(),
            id="generate_daily_reports_startup",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
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
                    finally:
                        break

            async def run_notification_delivery_job() -> None:
                logger.info("Notification delivery started")
                async for db in get_db():
                    try:
                        sent, failed = await send_pending_notifications(db)
                        logger.info("Notification delivery completed (sent=%s, failed=%s)", sent, failed)
                    except Exception as exc:
                        logger.error("Notification delivery failed: %s", exc, exc_info=True)
                    finally:
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
            f"(prices:5m, news:1h, reports: every {settings.REPORT_SCHEDULER_INTERVAL_HOURS} hours)"
        )
    else:
        print("[lifespan] scheduler skipped")

    app.state.scheduler = scheduler

    try:
        yield
    finally:
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
    return {"status": "ok", "project": settings.PROJECT_NAME}


@app.get("/db-check")
async def db_check(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(text("SELECT 1"))
        value = result.scalar()
        if value == 1:
            return {"status": "db_connected"}
        return {"status": "error", "message": "Unexpected result"}
    except Exception:
        logger.warning("Database connectivity check failed")
        return {"status": "error", "message": "Database connectivity check failed."}


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

        # Macro routing: KR bonds / US bonds / commodities
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
            data = await fetch_us_bond_data(asset_ticker)
            history_prices = data.get("history_prices", [])
            if not history_prices:
                raise HTTPException(status_code=404, detail=f"No US bond history found for ticker: {asset_ticker}")
            points = build_points(history_prices)
            return {
                "ticker": asset_ticker,
                "series_type": "yield",
                "unit": "%",
                "points": points,
                "legacy": [{"date": p["date"], "close": p["value"], "value": p["value"]} for p in points],
            }
        elif asset_ticker in ["XAU", "XAG", "GC=F", "SI=F"]:
            data = await fetch_commodity_data(asset_ticker)
            history_prices = data.get("history_prices", [])
            if not history_prices:
                raise HTTPException(status_code=404, detail=f"No commodity history found for ticker: {asset_ticker}")
            points = build_points(history_prices)
            return {
                "ticker": asset_ticker,
                "series_type": "price",
                "unit": "USD",
                "points": points,
                "legacy": [{"date": p["date"], "close": p["value"], "value": p["value"]} for p in points],
            }

        # Default path: yfinance stock/crypto history
        if period == "1d":
            interval = "5m"
        elif period == "1mo" or period == "1y":
            interval = "1d"
        elif period == "5y":
            interval = "1wk"
        else:
            interval = "1d"

        stock = yf.Ticker(asset_ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty:
            return []

        result = []
        for index, row in df.iterrows():
            date_str = index.strftime("%Y-%m-%d %H:%M") if period == "1d" else index.strftime("%Y-%m-%d")
            result.append({
                "date": date_str,
                "value": float(row["Close"]),
            })
        return {
            "ticker": asset_ticker,
            "series_type": "price",
            "unit": "USD",
            "points": result,
            "legacy": [{"date": p["date"], "close": p["value"], "value": p["value"]} for p in result],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

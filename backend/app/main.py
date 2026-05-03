from contextlib import asynccontextmanager
import logging
from datetime import datetime, timedelta

import yfinance as yf
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .core.cache import market_cache
from .core.config import settings
from .db.session import engine, get_db
from .models import AIReport, Asset, Base
from .services.ai_service import generate_daily_reports, generate_report_for_ticker
from .services.market_service import update_news_task, update_prices_task
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
from .api import auth, community
from .models import User
from .api.deps import get_current_user

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            # await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        print("[lifespan] database initialization completed")
    except Exception as exc:
        print(f"[lifespan] database initialization skipped: {exc}")

    print("[lifespan] initial market cache warm-up started")
    await update_prices_task()
    await update_news_task()
    print("[lifespan] initial market cache warm-up completed")

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
        hours=6,
        id="generate_daily_reports",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    print("[lifespan] scheduler started (prices:5m, news:1h, reports: every 6 hours)")

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        print("[lifespan] scheduler stopped")


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(community.router)


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
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/market/prices")
async def get_market_prices():
    return market_cache["prices"]


@app.get("/api/market/news")
async def get_market_news():
    return market_cache["news"]


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


@app.post("/api/ai/generate/{ticker}")
async def generate_report(ticker: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await generate_report_for_ticker(ticker, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("리포트 생성 API 실패 (ticker=%s): %s", ticker, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate report for {ticker}") from exc

    return {
        "status": "success",
        "message": "리포트 생성 및 DB 저장 완료",
        "data": result["final_report"],
    }


@app.get("/api/reports/{ticker}")
async def get_latest_report(ticker: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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
    }

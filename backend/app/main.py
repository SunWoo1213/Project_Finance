from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .core.cache import market_cache
from .core.config import settings
from .db.session import AsyncSessionLocal, engine, get_db
from .models import AIReport, Asset, Base
from .services.ai_service import generate_daily_reports, generate_report_for_ticker
from .services.market_service import update_news_task, update_prices_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
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
        async with AsyncSessionLocal() as db_session:
            await generate_daily_reports(db_session)

    scheduler.add_job(
        run_daily_reports_job,
        "cron",
        hour=8,
        minute=0,
        id="generate_daily_reports",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    print("[lifespan] scheduler started (prices:5m, news:1h, reports:daily 08:00)")

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        print("[lifespan] scheduler stopped")


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)


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


@app.post("/api/ai/generate/{ticker}")
async def generate_report(ticker: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await generate_report_for_ticker(ticker, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "status": "success",
        "message": "리포트 생성 및 DB 저장 완료",
        "data": result["final_report"],
    }


@app.get("/api/reports/{ticker}")
async def get_latest_report(ticker: str, db: AsyncSession = Depends(get_db)):
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

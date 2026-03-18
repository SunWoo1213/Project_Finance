import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.cache import market_cache
from ..models import AIReport, Asset
from .graph.graph import app as graph_app
from .graph.state import AgentState
from .market_service import KR_TOP10, US_TOP10


def find_cached_payload(cache_bucket: dict, ticker: str):
    for group_data in cache_bucket.values():
        for label, item in group_data.items():
            if label == ticker or item.get("symbol") == ticker:
                return item
    return None


async def generate_report_for_ticker(ticker: str, db: AsyncSession) -> dict:
    price_payload = find_cached_payload(market_cache["prices"], ticker)
    news_payload = find_cached_payload(market_cache["news"], ticker)
    if not price_payload or not news_payload:
        raise ValueError(f"No cached market data found for ticker: {ticker}")

    initial_state: AgentState = {
        "ticker": ticker,
        "price_data": {
            "price": price_payload.get("price"),
            "change_pct": price_payload.get("change_pct"),
            "symbol": price_payload.get("symbol"),
        },
        "news_data": news_payload.get("items", []),
        "bull_analysis": "",
        "bear_analysis": "",
        "final_report": "",
    }

    result = await asyncio.to_thread(graph_app.invoke, initial_state)

    asset_result = await db.execute(select(Asset).where(Asset.ticker == ticker))
    asset = asset_result.scalar_one_or_none()
    if asset is None:
        asset = Asset(ticker=ticker, name=ticker, asset_type="stock")
        db.add(asset)

    await db.flush()

    report = AIReport(
        asset_id=asset.id,
        bull_summary=result["bull_analysis"],
        bear_summary=result["bear_analysis"],
        final_content=result["final_report"],
    )
    db.add(report)
    await db.commit()

    return result


async def generate_daily_reports(db_session: AsyncSession) -> None:
    tickers = list(US_TOP10.keys()) + list(KR_TOP10.keys())
    for ticker in tickers:
        try:
            await generate_report_for_ticker(ticker, db_session)
            print(f"[generate_daily_reports] report created for {ticker}")
        except Exception as exc:
            await db_session.rollback()
            print(f"[generate_daily_reports] {ticker} failed: {exc}")
        await asyncio.sleep(2)

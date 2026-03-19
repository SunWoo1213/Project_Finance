import asyncio
import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.cache import market_cache
from ..db.session import AsyncSessionLocal
from ..models import AIReport, Asset, AssetCategory
from .graph.graph import app as graph_app
from .market_service import BONDS, COMMODITIES, CRYPTOS, INDICES, KR_BONDS, KR_TOP10

logger = logging.getLogger(__name__)


def get_asset_category(ticker: str) -> AssetCategory:
    if ticker in list(INDICES.values()):
        return AssetCategory.INDEX
    if ticker in list(BONDS.values()):
        return AssetCategory.BOND_US
    if ticker in list(KR_BONDS.values()):
        return AssetCategory.BOND_KR
    if ticker in list(COMMODITIES.values()):
        return AssetCategory.COMMODITY
    if ticker in list(CRYPTOS.values()):
        return AssetCategory.CRYPTO
    if ticker in list(KR_TOP10.values()):
        return AssetCategory.STOCK_KR
    return AssetCategory.STOCK_US


def find_cached_payload(cache_bucket: dict, ticker: str):
    for group_data in cache_bucket.values():
        for label, item in group_data.items():
            if label == ticker or item.get("symbol") == ticker:
                return item
    return None


async def generate_report_for_ticker(ticker: str, db: AsyncSession) -> dict:
    price_payload = find_cached_payload(market_cache["prices"], ticker)
    news_payload = find_cached_payload(market_cache["news"], ticker)
    if not price_payload:
        raise ValueError(f"No cached market data found for ticker: {ticker}")

    last_report_result = await db.execute(
        select(AIReport.final_content)
        .join(Asset, AIReport.asset_id == Asset.id)
        .where(Asset.ticker == ticker)
        .order_by(AIReport.created_at.desc())
        .limit(1)
    )
    previous_report = last_report_result.scalar_one_or_none() or ""

    category = get_asset_category(ticker)

    initial_state = {
        "ticker": ticker,
        "category": category.name,
        "price_data": {
            "price": price_payload.get("price"),
            "change_pct": price_payload.get("change_pct"),
            "symbol": price_payload.get("symbol"),
        },
        "news_data": (news_payload or {}).get("items", []),
        "asset_category": category.name,
        "financial_context": "",
        "news_context": "",
        "macro_context": "",
        "structured_facts": {},
        "draft_report": "",
        "previous_report": previous_report,
        "analysis_result": "",
        "final_report": "",
        "feedback": "",
        "revision_count": 0,
        "retry_count": 0,
        "is_pass": False,
    }

    config = {"configurable": {"thread_id": ticker}}
    result = await graph_app.ainvoke(initial_state, config=config)

    asset_result = await db.execute(select(Asset).where(Asset.ticker == ticker))
    asset = asset_result.scalar_one_or_none()
    if asset is None:
        asset = Asset(ticker=ticker, name=price_payload.get("symbol", ticker), category=category)
        db.add(asset)

    await db.flush()

    report = AIReport(
        asset_id=asset.id,
        bull_summary=result.get("analysis_result", "")[:500],
        bear_summary="리스크 요인 분석은 본문에 통합",
        final_content=result["final_report"],
    )
    db.add(report)
    await db.commit()

    return result


async def generate_daily_reports() -> None:
    logger.info("AI 리포트 생성 시작")
    try:
        today = datetime.now().date()
        async with AsyncSessionLocal() as db_session:
            assets_result = await db_session.execute(select(Asset).order_by(Asset.id.asc()))
            assets = assets_result.scalars().all()
            logger.info("리포트 생성 대상 자산 수: %d", len(assets))

            for asset in assets:
                try:
                    existing_report_result = await db_session.execute(
                        select(AIReport.id)
                        .where(
                            AIReport.asset_id == asset.id,
                            func.date(AIReport.created_at) == today,
                        )
                        .limit(1)
                    )
                    if existing_report_result.scalar_one_or_none() is not None:
                        logger.info("%s 오늘 리포트 이미 존재 - 건너뜀", asset.ticker)
                        continue

                    logger.info("%s 리포트 생성 시작", asset.ticker)
                    await generate_report_for_ticker(asset.ticker, db_session)
                    logger.info("%s 리포트 생성 완료", asset.ticker)

                    # Rate-limit protection between LLM calls.
                    await asyncio.sleep(10)
                except Exception as exc:
                    await db_session.rollback()
                    logger.error(f"{asset.ticker} 리포트 실패: {exc}", exc_info=True)

        logger.info("AI 리포트 생성 종료")
    except Exception as exc:
        logger.error(f"리포트 생성 중 에러 발생: {exc}", exc_info=True)

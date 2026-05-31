import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.cache import market_cache
from ..db.session import AsyncSessionLocal
from ..models import AIReport, Asset, AssetCategory
from .graph.graph import app as graph_app
from .market_service import BONDS, COMMODITIES, CRYPTOS, INDICES, KR_BONDS, KR_TOP10, fetch_latest_asset_context

logger = logging.getLogger(__name__)


ASSET_FACT_REQUIREMENTS: dict[str, dict[str, list[str]]] = {
    "STOCK_US": {
        "required": ["price", "recent_performance", "market_cap", "company_news", "valuation_or_beta"],
        "optional": ["revenue", "earnings", "margins", "guidance", "earnings_date", "management_commentary"],
    },
    "STOCK_KR": {
        "required": ["price", "recent_performance", "sector_or_local_context", "company_news"],
        "optional": ["fx_sensitivity", "rate_sensitivity", "financial_statement_context"],
    },
    "INDEX": {
        "required": ["index_level", "recent_performance", "macro_drivers"],
        "optional": ["sector_leadership", "rates", "fx", "volatility", "liquidity"],
    },
    "BOND_US": {
        "required": ["yield_level", "curve_context", "central_bank_policy", "inflation_context"],
        "optional": ["real_rate_context", "price_return_context"],
    },
    "BOND_KR": {
        "required": ["yield_level", "curve_context", "central_bank_policy", "inflation_context"],
        "optional": ["real_rate_context", "fx_context", "price_return_context"],
    },
    "COMMODITY": {
        "required": ["spot_or_futures_price", "dollar_context", "real_rates", "supply_demand_driver"],
        "optional": ["inventory_context", "geopolitical_context", "seasonality"],
    },
    "CRYPTO": {
        "required": ["price", "volume_or_liquidity", "regulatory_or_etf_news", "liquidity_backdrop"],
        "optional": ["onchain_data", "exchange_data"],
    },
}


class ReportQualityError(Exception):
    def __init__(self, ticker: str, feedback: str, revision_count: int, metadata: dict[str, Any]):
        super().__init__(f"Report generation rejected by evaluator for {ticker}: {feedback}")
        self.ticker = ticker
        self.feedback = feedback
        self.revision_count = revision_count
        self.metadata = metadata


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


def merge_news_items(*groups: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for group in groups:
        for item in group or []:
            key = str(item.get("link") or item.get("title") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged[:12]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_report_facts(
    ticker: str,
    category: AssetCategory,
    price_payload: dict[str, Any],
    merged_news: list[dict[str, Any]],
    latest_context: dict[str, Any],
) -> dict[str, Any]:
    price_as_of = market_cache.get("last_updated", {}).get("prices") or _iso_now()
    news_as_of = (
        latest_context.get("fetched_at")
        or market_cache.get("last_updated", {}).get("news")
        or price_as_of
    )
    source_status = {
        "price": "cached" if price_payload else "missing",
        "market_cache_prices_as_of": price_as_of,
        "market_cache_news_as_of": market_cache.get("last_updated", {}).get("news"),
        "latest_context": latest_context.get("source_status", "unknown"),
        "latest_context_source": latest_context.get("source", "unknown"),
    }
    requirements = ASSET_FACT_REQUIREMENTS.get(category.name, {"required": ["price"], "optional": []})

    data_limitations: list[str] = []
    if not price_payload.get("price") and not price_payload.get("currentPrice"):
        data_limitations.append("가격 데이터가 캐시에 없거나 0으로 제공되었습니다.")
    if not merged_news:
        data_limitations.append("최근 뉴스 데이터가 비어 있어 뉴스 기반 해석의 신뢰도가 낮습니다.")
    if latest_context.get("source_status") not in (None, "fresh"):
        data_limitations.append(f"최신 컨텍스트 수집 상태: {latest_context.get('source_status')}")
    if category.name == "STOCK_KR":
        data_limitations.append("국내 개별주 재무제표와 가이던스는 현재 무료 provider 기반 구조화 수집 범위 밖입니다.")
    if category.name in {"BOND_US", "BOND_KR"}:
        data_limitations.append("채권 데이터는 가격 수익률과 수익률 변동을 구분해 해석해야 합니다.")
    if category.name == "COMMODITY":
        data_limitations.append("재고와 공급망 데이터는 현재 구조화 provider로 직접 수집하지 않습니다.")
    if category.name == "CRYPTO":
        data_limitations.append("온체인/거래소 데이터는 신뢰 가능한 provider가 없으면 사용하지 않습니다.")

    missing_required: list[str] = []
    if not price_payload.get("price") and not price_payload.get("currentPrice"):
        missing_required.append("price")
    if "market_cap" in requirements["required"] and not price_payload.get("marketCap"):
        missing_required.append("market_cap")
    if "volume_or_liquidity" in requirements["required"] and not price_payload.get("volume"):
        missing_required.append("volume_or_liquidity")
    if "company_news" in requirements["required"] and not merged_news:
        missing_required.append("company_news")
    if missing_required:
        data_limitations.append(f"필수 팩트 일부가 비어 있습니다: {', '.join(sorted(set(missing_required)))}")

    news_items = []
    for item in merged_news:
        news_items.append(
            {
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "as_of": item.get("published_at") or news_as_of,
                "source": item.get("source", "unknown"),
                "url": item.get("link") or item.get("url") or "",
                "confidence": "medium" if item.get("title") else "low",
            }
        )

    events = []
    for item in latest_context.get("events", []):
        events.append(
            {
                "title": item.get("title", ""),
                "value": item.get("value", ""),
                "as_of": news_as_of,
                "source": item.get("source", latest_context.get("source", "unknown")),
                "confidence": "medium",
            }
        )

    return {
        "ticker": ticker,
        "asset_category": category.name,
        "requirements": requirements,
        "price": {
            "value": price_payload.get("price", price_payload.get("currentPrice")),
            "change_pct": price_payload.get("change_pct", price_payload.get("changePercent")),
            "as_of": price_as_of,
            "source": "market_cache",
            "url": "",
            "confidence": "high" if price_payload else "low",
        },
        "market": {
            "market_cap": {
                "value": price_payload.get("marketCap"),
                "as_of": price_as_of,
                "source": "market_cache",
                "confidence": "medium" if price_payload.get("marketCap") else "low",
            },
            "history_points": {
                "value": len(price_payload.get("history_prices") or []),
                "as_of": price_as_of,
                "source": "market_cache",
                "confidence": "medium" if price_payload.get("history_prices") else "low",
            },
        },
        "valuation": [],
        "financials": [],
        "news": news_items,
        "macro": [],
        "events": events,
        "risks": [],
        "data_limitations": data_limitations,
        "missing_required_facts": sorted(set(missing_required)),
        "source_status": source_status,
    }


def _stringify_summary_item(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("title", "summary", "value"):
            if item.get(key):
                return str(item[key])
        return ", ".join(f"{key}: {value}" for key, value in item.items() if value)
    return str(item)


def _summary_from_facts(items: list[Any] | None, fallback: str = "") -> str:
    cleaned = [_stringify_summary_item(item).strip() for item in items or []]
    cleaned = [item for item in cleaned if item]
    summary = "\n".join(f"- {item}" for item in cleaned[:5])
    return (summary or fallback)[:500]


def _build_generation_metadata(
    ticker: str,
    report_facts: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    structured_facts = result.get("structured_facts") or {}
    data_as_of = (
        structured_facts.get("data_as_of")
        or report_facts.get("price", {}).get("as_of")
        or _iso_now()
    )
    return {
        "ticker": ticker,
        "is_pass": bool(result.get("is_pass")),
        "feedback": result.get("feedback", ""),
        "fact_check_pass": bool(result.get("fact_check_pass")),
        "fact_check_feedback": result.get("fact_check_feedback", ""),
        "revision_count": int(result.get("revision_count", 0) or 0),
        "generated_at": _iso_now(),
        "data_as_of": data_as_of,
        "source_status": report_facts.get("source_status", {}),
        "missing_required_facts": report_facts.get("missing_required_facts", []),
        "risk_summary": _summary_from_facts(
            structured_facts.get("risk_factors") or structured_facts.get("risks"),
            "구조화된 리스크 요약이 생성되지 않았습니다.",
        ),
    }


async def generate_report_for_ticker(ticker: str, db: AsyncSession) -> dict:
    price_payload = find_cached_payload(market_cache["prices"], ticker)
    news_payload = find_cached_payload(market_cache["news"], ticker)
    if not price_payload:
        raise ValueError(f"No cached market data found for ticker: {ticker}")

    latest_context = await fetch_latest_asset_context(ticker)
    merged_news = merge_news_items((news_payload or {}).get("items", []), latest_context.get("news", []))

    last_report_result = await db.execute(
        select(AIReport.final_content)
        .join(Asset, AIReport.asset_id == Asset.id)
        .where(Asset.ticker == ticker)
        .order_by(AIReport.created_at.desc())
        .limit(1)
    )
    previous_report = last_report_result.scalar_one_or_none() or ""

    category = get_asset_category(ticker)
    report_facts = _build_report_facts(ticker, category, price_payload, merged_news, latest_context)

    initial_state = {
        "ticker": ticker,
        "category": category.name,
        "price_data": {
            "price": price_payload.get("price"),
            "change_pct": price_payload.get("change_pct"),
            "symbol": price_payload.get("symbol"),
        },
        "news_data": merged_news,
        "latest_context": latest_context,
        "asset_category": category.name,
        "report_facts": report_facts,
        "generation_metadata": {},
        "financial_context": "",
        "news_context": "",
        "macro_context": "",
        "financial_facts": {},
        "news_facts": {},
        "macro_facts": {},
        "structured_facts": {},
        "draft_report": "",
        "fact_check_pass": False,
        "fact_check_feedback": "",
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
    metadata = _build_generation_metadata(ticker, report_facts, result)
    result["generation_metadata"] = metadata

    if not result.get("is_pass"):
        raise ReportQualityError(
            ticker=ticker,
            feedback=metadata["feedback"],
            revision_count=metadata["revision_count"],
            metadata=metadata,
        )

    asset_result = await db.execute(select(Asset).where(Asset.ticker == ticker))
    asset = asset_result.scalar_one_or_none()
    if asset is None:
        asset = Asset(ticker=ticker, name=price_payload.get("symbol", ticker), category=category)
        db.add(asset)

    await db.flush()
    structured_facts = result.get("structured_facts") or {}

    report = AIReport(
        asset_id=asset.id,
        bull_summary=_summary_from_facts(
            structured_facts.get("bull_factors"),
            result.get("analysis_result", ""),
        ),
        bear_summary=_summary_from_facts(
            structured_facts.get("bear_factors"),
            "구조화된 하락 요약이 생성되지 않았습니다.",
        ),
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

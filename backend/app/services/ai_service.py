import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.cache import market_cache
from ..core.config import settings
from ..db.session import AsyncSessionLocal
from ..models import AIReport, Asset, AssetCategory
from .graph.graph import app as graph_app
from .graph.nodes import (
    _find_unsupported_numbers,
    _find_unsupported_qualitative_claims,
    _missing_framework_sections,
    _missing_report_sections,
    sanitize_unsupported_numbers,
)
from .market_service import (
    BONDS,
    COMMODITIES,
    CRYPTOS,
    INDICES,
    KR_BONDS,
    KR_TOP10,
    ensure_price_cache_for_ticker,
    fetch_latest_asset_context,
)

logger = logging.getLogger(__name__)


SCHEDULED_REPORT_ASSET_CATALOG: dict[str, dict[str, Any]] = {
    "DGS10": {"name": "US 10Y Treasury", "category": AssetCategory.BOND_US},
    "XAU": {"name": "Gold", "category": AssetCategory.COMMODITY},
    "BTC-USD": {"name": "Bitcoin", "category": AssetCategory.CRYPTO},
    "NVDA": {"name": "NVDA", "category": AssetCategory.STOCK_US},
    "005930.KS": {"name": "Samsung Electronics", "category": AssetCategory.STOCK_KR},
}

SCHEDULED_REPORT_TICKER_ALIASES = {
    "GC=F": "XAU",
    "GOLD": "XAU",
    "BITCOIN": "BTC-USD",
    "BTC": "BTC-USD",
    "SAMSUNG": "005930.KS",
    "005930": "005930.KS",
}


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


PRIMARY_FACT_KEYS = {
    "price",
    "index_level",
    "yield_level",
    "spot_or_futures_price",
}

FACT_COLLECTOR_SOURCE_BY_KEY = {
    "price": "market_cache.prices",
    "index_level": "market_cache.prices",
    "yield_level": "market_cache.prices",
    "spot_or_futures_price": "market_cache.prices",
    "recent_performance": "market_cache.prices.history",
    "market_cap": "market_cache.prices.marketCap",
    "company_news": "market_cache.news/latest_context.news",
    "volume_or_liquidity": "market_cache.prices.volume",
    "regulatory_or_etf_news": "latest_context.news",
    "liquidity_backdrop": "latest_context.news",
    "macro_drivers": "latest_context.events",
    "curve_context": "latest_context.events",
    "central_bank_policy": "latest_context.events",
    "inflation_context": "latest_context.events",
    "dollar_context": "latest_context.events",
    "real_rates": "latest_context.events",
    "supply_demand_driver": "latest_context.news",
}


ASSET_ANALYSIS_FRAMEWORKS: dict[str, dict[str, list[str] | str]] = {
    "STOCK_US": {
        "label": "US stock equity framework",
        "required_sections": [
            "가격과 최근 성과",
            "밸류에이션과 시가총액",
            "실적, 마진, 가이던스",
            "회사 뉴스와 경영진 코멘트",
            "금리와 달러 환경",
        ],
        "interpretation_rules": [
            "주가 방향과 기업 펀더멘털을 분리해 설명합니다.",
            "밸류에이션 수치가 없으면 고평가/저평가 단정을 피합니다.",
            "실적 데이터가 없으면 데이터 한계로 명시합니다.",
        ],
    },
    "STOCK_KR": {
        "label": "Korean stock local-market framework",
        "required_sections": [
            "가격과 최근 성과",
            "업종과 국내 시장 맥락",
            "기업 뉴스",
            "환율 민감도",
            "금리 민감도",
        ],
        "interpretation_rules": [
            "국내 개별주 재무제표 공백을 추정으로 채우지 않습니다.",
            "원화, 수출, 금리 영향을 관련성이 있을 때만 연결합니다.",
            "로컬 뉴스가 부족하면 신뢰도 한계를 상단에 노출합니다.",
        ],
    },
    "INDEX": {
        "label": "Index macro and breadth framework",
        "required_sections": [
            "지수 레벨과 최근 성과",
            "섹터 주도력",
            "금리와 환율",
            "변동성과 유동성",
            "거시 이벤트",
        ],
        "interpretation_rules": [
            "개별 기업 실적처럼 해석하지 않습니다.",
            "지수 상승/하락을 섹터, 금리, 유동성 맥락으로 나눕니다.",
            "섹터 주도력 데이터가 없으면 한계로 명시합니다.",
        ],
    },
    "BOND_US": {
        "label": "US bond yield framework",
        "required_sections": [
            "수익률 레벨",
            "수익률 곡선",
            "연준 정책",
            "CPI와 실질금리",
            "가격 수익률과 수익률 변동 구분",
        ],
        "interpretation_rules": [
            "채권 가격과 수익률은 반대로 움직일 수 있음을 명시합니다.",
            "수익률 변화를 주식 가격 변화처럼 표현하지 않습니다.",
            "정책과 물가 데이터가 부족하면 방향성 단정을 피합니다.",
        ],
    },
    "BOND_KR": {
        "label": "Korean bond yield framework",
        "required_sections": [
            "수익률 레벨",
            "수익률 곡선",
            "한국은행 정책",
            "물가와 원화 환율",
            "가격 수익률과 수익률 변동 구분",
        ],
        "interpretation_rules": [
            "채권 가격과 수익률은 반대로 움직일 수 있음을 명시합니다.",
            "한국은행 정책과 국내 물가 맥락을 우선합니다.",
            "환율 영향은 관련성이 있을 때만 연결합니다.",
        ],
    },
    "COMMODITY": {
        "label": "Commodity supply-demand framework",
        "required_sections": [
            "현물 또는 선물 가격",
            "달러와 실질금리",
            "재고와 공급망",
            "지정학 리스크",
            "계절성",
        ],
        "interpretation_rules": [
            "원자재 가격을 기업 실적 논리로 설명하지 않습니다.",
            "공급, 수요, 달러, 실질금리 요인을 분리합니다.",
            "재고 데이터가 없으면 공급 수요 판단을 제한합니다.",
        ],
    },
    "CRYPTO": {
        "label": "Crypto liquidity and regulation framework",
        "required_sections": [
            "가격과 거래량",
            "유동성 환경",
            "ETF와 규제 뉴스",
            "리스크온/오프 심리",
            "온체인 또는 거래소 데이터 한계",
        ],
        "interpretation_rules": [
            "온체인 데이터가 없으면 온체인 근거를 만들지 않습니다.",
            "암호화폐 가격을 기업 펀더멘털처럼 설명하지 않습니다.",
            "규제와 ETF 뉴스는 확인된 경우에만 촉매로 사용합니다.",
        ],
    },
}


class ReportQualityError(Exception):
    def __init__(self, ticker: str, feedback: str, revision_count: int, metadata: dict[str, Any]):
        super().__init__(f"Report generation rejected by evaluator for {ticker}: {feedback}")
        self.ticker = ticker
        self.feedback = feedback
        self.revision_count = revision_count
        self.metadata = metadata


class ReportReadinessError(Exception):
    def __init__(self, ticker: str, metadata: dict[str, Any]):
        super().__init__(f"Report generation blocked for {ticker}: insufficient data")
        self.ticker = ticker
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


def _configured_scheduled_report_tickers() -> list[str]:
    raw_tickers = str(settings.REPORT_SCHEDULER_TARGET_TICKERS or "").split(",")
    tickers: list[str] = []
    seen: set[str] = set()
    for raw_ticker in raw_tickers:
        ticker = raw_ticker.strip()
        if not ticker:
            continue
        ticker = SCHEDULED_REPORT_TICKER_ALIASES.get(ticker.upper(), ticker)
        if ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    return tickers


def _scheduled_report_asset_spec(ticker: str) -> dict[str, Any]:
    catalog_spec = SCHEDULED_REPORT_ASSET_CATALOG.get(ticker)
    if catalog_spec:
        return {"ticker": ticker, **catalog_spec}
    return {"ticker": ticker, "name": ticker, "category": get_asset_category(ticker)}


async def ensure_scheduled_report_assets(db: AsyncSession) -> list[Asset]:
    scheduled_assets: list[Asset] = []
    for ticker in _configured_scheduled_report_tickers():
        spec = _scheduled_report_asset_spec(ticker)
        result = await db.execute(select(Asset).where(Asset.ticker == spec["ticker"]))
        asset = result.scalar_one_or_none()
        if asset is None:
            asset = Asset(
                ticker=spec["ticker"],
                name=spec["name"],
                category=spec["category"],
            )
            db.add(asset)
            await db.flush()
        else:
            asset.name = spec["name"]
            asset.category = spec["category"]
        scheduled_assets.append(asset)

    await db.commit()
    return scheduled_assets


def _scheduled_report_jobs(assets: list[Asset]) -> list[dict[str, Any]]:
    return [{"asset_id": asset.id, "ticker": asset.ticker} for asset in assets]


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


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _has_positive_value(value: Any) -> bool:
    if value in (None, ""):
        return False
    try:
        return float(value) != 0
    except (TypeError, ValueError):
        return bool(value)


def _fact_is_present(
    fact_key: str,
    price_payload: dict[str, Any],
    merged_news: list[dict[str, Any]],
    latest_context: dict[str, Any],
) -> bool:
    price_value = price_payload.get("price", price_payload.get("currentPrice"))
    change_value = price_payload.get("change_pct", price_payload.get("changePercent"))
    history_points = price_payload.get("history_prices") or []
    latest_news = latest_context.get("news") or []
    latest_events = latest_context.get("events") or []

    if fact_key in PRIMARY_FACT_KEYS:
        return _has_positive_value(price_value)
    if fact_key == "recent_performance":
        return change_value is not None or len(history_points) > 1
    if fact_key == "market_cap":
        return _has_positive_value(price_payload.get("marketCap"))
    if fact_key == "volume_or_liquidity":
        return _has_positive_value(price_payload.get("volume"))
    if fact_key in {"company_news", "regulatory_or_etf_news", "supply_demand_driver"}:
        return bool(merged_news or latest_news)
    if fact_key in {
        "macro_drivers",
        "curve_context",
        "central_bank_policy",
        "inflation_context",
        "dollar_context",
        "real_rates",
        "sector_or_local_context",
        "liquidity_backdrop",
    }:
        return bool(latest_events or latest_news)
    return False


def _build_fact_matrix(
    category: AssetCategory,
    requirements: dict[str, list[str]],
    price_payload: dict[str, Any],
    merged_news: list[dict[str, Any]],
    latest_context: dict[str, Any],
) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for requirement, fact_keys in (
        ("required", requirements.get("required", [])),
        ("optional", requirements.get("optional", [])),
    ):
        for fact_key in fact_keys:
            is_present = _fact_is_present(fact_key, price_payload, merged_news, latest_context)
            if is_present:
                status = "present"
            elif requirement == "required":
                status = "missing_required"
            else:
                status = "missing_optional_provider"

            matrix.append(
                {
                    "fact_key": fact_key,
                    "display_label": fact_key.replace("_", " ").title(),
                    "asset_categories": [category.name],
                    "collector_source": FACT_COLLECTOR_SOURCE_BY_KEY.get(fact_key, "provider_not_configured"),
                    "requirement": requirement,
                    "status": status,
                    "stale_after_hours": settings.REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS,
                    "blocking_severity": "blocking" if fact_key in PRIMARY_FACT_KEYS else "limiting",
                    "ui_note": (
                        "Required before report generation."
                        if requirement == "required"
                        else "Optional provider coverage; show as limitation when missing."
                    ),
                }
            )
    return matrix


def _fact_matrix_summary(fact_matrix: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "present": 0,
        "missing_required": 0,
        "missing_optional_provider": 0,
        "not_applicable": 0,
    }
    for item in fact_matrix:
        status = item.get("status", "not_applicable")
        summary[status] = summary.get(status, 0) + 1
    return summary


def _grade_report_readiness(report_facts: dict[str, Any]) -> dict[str, Any]:
    price_value = (report_facts.get("price") or {}).get("value")
    fact_matrix = list(report_facts.get("fact_matrix") or [])
    missing_required = [
        item.get("fact_key")
        for item in fact_matrix
        if item.get("status") == "missing_required" and item.get("fact_key")
    ] or list(report_facts.get("missing_required_facts") or [])
    data_limitations = list(report_facts.get("data_limitations") or [])
    asset_category = report_facts.get("asset_category", "")

    blocking_reasons: list[str] = []
    limiting_reasons: list[str] = []

    if price_value in (None, "", 0):
        blocking_reasons.append("가격 데이터가 없어 리포트 생성을 중단했습니다.")

    blocking_fact_keys = [
        item.get("fact_key")
        for item in fact_matrix
        if item.get("status") == "missing_required" and item.get("blocking_severity") == "blocking"
    ]
    if blocking_fact_keys:
        blocking_reasons.append(f"Blocking facts are missing: {', '.join(blocking_fact_keys)}")

    if missing_required:
        limiting_reasons.append(f"필수 팩트 일부가 비어 있습니다: {', '.join(missing_required)}")
    if data_limitations:
        limiting_reasons.extend(data_limitations[:3])

    if asset_category in {"CRYPTO", "COMMODITY"} and len(missing_required) >= 3:
        blocking_reasons.append("해당 자산군의 핵심 유동성/공급 데이터가 너무 부족합니다.")

    if blocking_reasons:
        status = "blocked"
    elif limiting_reasons:
        status = "limited"
    else:
        status = "ready"

    return {
        "status": status,
        "blocking_reasons": blocking_reasons,
        "limiting_reasons": limiting_reasons,
        "missing_required_facts": missing_required,
        "fact_matrix_summary": _fact_matrix_summary(fact_matrix),
    }


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
    analysis_framework = ASSET_ANALYSIS_FRAMEWORKS.get(
        category.name,
        {
            "label": "Generic asset framework",
            "required_sections": ["가격", "뉴스", "거시 환경", "리스크"],
            "interpretation_rules": ["자산군에 맞지 않는 해석을 피하고 데이터 한계를 명시합니다."],
        },
    )

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

    fact_matrix = _build_fact_matrix(category, requirements, price_payload, merged_news, latest_context)
    missing_required = [
        item["fact_key"]
        for item in fact_matrix
        if item.get("status") == "missing_required"
    ]
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
        "analysis_framework": analysis_framework,
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
        "fact_matrix": fact_matrix,
        "fact_matrix_summary": _fact_matrix_summary(fact_matrix),
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


def _blocked_research_packet(report_facts: dict[str, Any]) -> dict[str, Any]:
    limitations = list(report_facts.get("data_limitations") or [])
    missing_required = list(report_facts.get("missing_required_facts") or [])
    return {
        "base_case": {
            "title": "Base case",
            "items": [],
            "evidence_ids": [],
            "limitation_reason": "Required source facts are missing.",
        },
        "bull_case": {
            "title": "Bull case",
            "items": [],
            "evidence_ids": [],
            "limitation_reason": "Generation stopped before scenario writing.",
        },
        "bear_case": {
            "title": "Bear case",
            "items": [],
            "evidence_ids": [],
            "limitation_reason": "Generation stopped before scenario writing.",
        },
        "risk_review": {
            "title": "Risk review",
            "items": limitations[:8],
            "evidence_ids": ["FACT_MATRIX"] if missing_required else [],
            "limitation_reason": "" if limitations else "No risk review was generated.",
        },
        "catalysts": [],
        "watchlist": missing_required,
        "source_table": [
            {
                "id": "FACT_MATRIX",
                "label": "Fact matrix",
                "source": "deterministic_readiness_gate",
                "status": "blocked",
            }
        ],
        "data_limitations": limitations,
        "prior_report_delta": {
            "items": [],
            "evidence_ids": [],
            "limitation_reason": "Generation stopped before prior-report comparison.",
        },
    }


def _build_generation_metadata(
    ticker: str,
    report_facts: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    structured_facts = result.get("structured_facts") or {}
    risk_review = result.get("risk_review") or {}
    research_packet = result.get("research_packet") or {}
    data_as_of = (
        structured_facts.get("data_as_of")
        or report_facts.get("price", {}).get("as_of")
        or _iso_now()
    )
    return {
        "ticker": ticker,
        "is_pass": bool(result.get("is_pass")),
        "quality_status": "pass" if result.get("is_pass") else "failed",
        "feedback": result.get("feedback", ""),
        "format_check_pass": bool(result.get("format_check_pass")),
        "format_check_feedback": result.get("format_check_feedback", ""),
        "fact_check_pass": bool(result.get("fact_check_pass")),
        "fact_check_feedback": result.get("fact_check_feedback", ""),
        "qualitative_check_pass": bool(result.get("qualitative_check_pass")),
        "qualitative_check_feedback": result.get("qualitative_check_feedback", ""),
        "revision_count": int(result.get("revision_count", 0) or 0),
        "generated_at": _iso_now(),
        "data_as_of": data_as_of,
        "source_status": report_facts.get("source_status", {}),
        "missing_required_facts": report_facts.get("missing_required_facts", []),
        "fact_matrix": report_facts.get("fact_matrix", []),
        "fact_matrix_summary": report_facts.get("fact_matrix_summary", {}),
        "readiness": report_facts.get("readiness", {}),
        "critic_mode": settings.REPORT_CRITIC_MODE,
        "llm_report_critics_enabled": settings.ENABLE_LLM_REPORT_CRITICS,
        "analysis_framework": report_facts.get("analysis_framework", {}),
        "research_packet": research_packet,
        "source_table": research_packet.get("source_table", []),
        "risk_summary": _summary_from_facts(
            (research_packet.get("risk_review") or {}).get("items")
            or risk_review.get("findings")
            or structured_facts.get("risk_factors")
            or structured_facts.get("risks"),
            "구조화된 리스크 요약이 생성되지 않았습니다.",
        ),
        "role_outputs": {
            "bull_thesis": result.get("bull_thesis") or {},
            "bear_thesis": result.get("bear_thesis") or {},
            "risk_review": risk_review,
        },
    }


def _attempt_numeric_sanitization_fallback(result: dict[str, Any]) -> dict[str, Any] | None:
    """fact_checker 루프 소진 시 미지원 숫자만 정제해 재검증 통과분만 살린다.

    포맷은 통과했으나 숫자 게이트에서만 탈락한(`format_check_pass=True`,
    `fact_check_pass=False`) 경우에 한해, 마지막 초안에서 미지원 숫자를 결정적으로
    정성 표현으로 치환한다. 그 뒤 포맷·숫자·정성 게이트를 모두 재검증해 전부 통과할
    때만 정제본을 반환한다(저장 대상). 하나라도 미통과면 ``None``을 돌려 기존
    미저장 경로(`ReportQualityError`)를 유지한다. LLM 재호출이 없어 비용은 불변이며
    저장되는 리포트는 항상 결정적 게이트를 통과한 상태다.
    """
    if not result.get("format_check_pass") or result.get("fact_check_pass"):
        return None

    draft = result.get("draft_report") or result.get("final_report") or ""
    if not draft:
        return None

    sanitized_draft = sanitize_unsupported_numbers(draft, result)
    removed = _find_unsupported_numbers(draft, result)

    # 정제본 전체 결정적 게이트 재검증.
    if _missing_report_sections(sanitized_draft):
        return None
    if _missing_framework_sections(sanitized_draft, result):
        return None
    if _find_unsupported_numbers(sanitized_draft, result):
        return None
    if _find_unsupported_qualitative_claims(sanitized_draft, result):
        return None

    updated = dict(result)
    updated["draft_report"] = sanitized_draft
    updated["analysis_result"] = sanitized_draft
    updated["final_report"] = sanitized_draft
    updated["is_pass"] = True
    updated["fact_check_pass"] = True
    updated["qualitative_check_pass"] = True
    updated["sanitized_numbers"] = removed
    existing_feedback = result.get("feedback", "")
    updated["feedback"] = (
        f"{existing_feedback}\n루프 소진 후 미지원 숫자를 정성 표현으로 정제하고 재검증을 통과해 저장함."
    ).strip()
    return updated


async def generate_report_for_ticker(ticker: str, db: AsyncSession) -> dict:
    if not settings.ENABLE_AI_REPORT_GENERATION:
        logger.info(
            "%s report generation blocked because ENABLE_AI_REPORT_GENERATION=false",
            ticker,
        )
        raise RuntimeError("AI report generation is disabled by ENABLE_AI_REPORT_GENERATION.")

    price_payload = find_cached_payload(market_cache["prices"], ticker)
    news_payload = find_cached_payload(market_cache["news"], ticker)
    if not price_payload:
        logger.info("%s market cache miss before report generation; attempting ticker-level cache fill", ticker)
        await ensure_price_cache_for_ticker(ticker)
        price_payload = find_cached_payload(market_cache["prices"], ticker)

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
    readiness = _grade_report_readiness(report_facts)
    report_facts["readiness"] = readiness
    if readiness["status"] == "blocked":
        blocked_packet = _blocked_research_packet(report_facts)
        metadata = {
            "ticker": ticker,
            "is_pass": False,
            "quality_status": "blocked",
            "feedback": "리포트 생성을 위한 필수 데이터가 부족합니다.",
            "format_check_pass": False,
            "format_check_feedback": "",
            "fact_check_pass": False,
            "fact_check_feedback": "",
            "qualitative_check_pass": False,
            "qualitative_check_feedback": "",
            "revision_count": 0,
            "generated_at": _iso_now(),
            "data_as_of": report_facts.get("price", {}).get("as_of") or _iso_now(),
            "source_status": report_facts.get("source_status", {}),
            "missing_required_facts": report_facts.get("missing_required_facts", []),
            "fact_matrix": report_facts.get("fact_matrix", []),
            "fact_matrix_summary": report_facts.get("fact_matrix_summary", {}),
            "readiness": readiness,
            "critic_mode": settings.REPORT_CRITIC_MODE,
            "llm_report_critics_enabled": settings.ENABLE_LLM_REPORT_CRITICS,
            "analysis_framework": report_facts.get("analysis_framework", {}),
            "research_packet": blocked_packet,
            "source_table": blocked_packet.get("source_table", []),
            "risk_summary": _summary_from_facts(report_facts.get("data_limitations"), "필수 데이터가 부족합니다."),
            "role_outputs": {"bull_thesis": {}, "bear_thesis": {}, "risk_review": {}},
        }
        raise ReportReadinessError(ticker=ticker, metadata=metadata)

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
        "bull_thesis": {},
        "bear_thesis": {},
        "risk_review": {},
        "research_packet": {},
        "draft_report": "",
        "format_check_pass": False,
        "format_check_feedback": "",
        "fact_check_pass": False,
        "fact_check_feedback": "",
        "qualitative_check_pass": False,
        "qualitative_check_feedback": "",
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
        sanitized = _attempt_numeric_sanitization_fallback(result)
        if sanitized is not None:
            result = sanitized
            metadata = _build_generation_metadata(ticker, report_facts, result)
            metadata["fallback_sanitized"] = True
            metadata["sanitized_numbers"] = result.get("sanitized_numbers", [])
            result["generation_metadata"] = metadata
            logger.info(
                "%s fact_checker 루프 소진 후 숫자 정제 폴백으로 저장 (sanitized=%s)",
                ticker,
                result.get("sanitized_numbers", []),
            )
        else:
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
            (result.get("bull_thesis") or {}).get("thesis") or structured_facts.get("bull_factors"),
            result.get("analysis_result", ""),
        ),
        bear_summary=_summary_from_facts(
            (result.get("bear_thesis") or {}).get("thesis") or structured_facts.get("bear_factors"),
            "구조화된 하락 요약이 생성되지 않았습니다.",
        ),
        final_content=result["final_report"],
        quality_status=metadata.get("quality_status"),
        quality_feedback=metadata.get("feedback", ""),
        format_check_pass=metadata.get("format_check_pass"),
        fact_check_pass=metadata.get("fact_check_pass"),
        qualitative_check_pass=metadata.get("qualitative_check_pass"),
        revision_count=metadata.get("revision_count"),
        data_as_of=_parse_iso_datetime(metadata.get("data_as_of")),
        source_summary=metadata.get("source_status", {}),
        risk_summary=metadata.get("risk_summary", ""),
        analysis_framework=metadata.get("analysis_framework", {}),
        metadata_json=metadata,
    )
    db.add(report)
    await db.commit()

    return result


async def generate_daily_reports() -> None:
    if not settings.ENABLE_AI_REPORT_GENERATION:
        logger.info("AI report generation skipped because ENABLE_AI_REPORT_GENERATION=false")
        return

    logger.info("AI 리포트 생성 시작")
    try:
        cooldown_cutoff = datetime.now() - timedelta(hours=settings.REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS)
        async with AsyncSessionLocal() as db_session:
            coverage = settings.REPORT_SCHEDULER_COVERAGE.lower().strip()
            if coverage != "conservative":
                logger.warning(
                    "REPORT_SCHEDULER_COVERAGE=%s requested, but broad scheduled generation remains disabled by policy.",
                    settings.REPORT_SCHEDULER_COVERAGE,
                )
            assets = await ensure_scheduled_report_assets(db_session)
            logger.info("리포트 생성 대상 자산 수: %d", len(assets))

            generated_count = 0
            for job in _scheduled_report_jobs(assets):
                asset_id = job["asset_id"]
                ticker = job["ticker"]
                if generated_count >= settings.REPORT_SCHEDULER_MAX_REPORTS_PER_RUN:
                    logger.info(
                        "스케줄러 회당 최대 리포트 수 도달 - max=%d",
                        settings.REPORT_SCHEDULER_MAX_REPORTS_PER_RUN,
                    )
                    break
                try:
                    existing_report_result = await db_session.execute(
                        select(AIReport.id)
                        .where(
                            AIReport.asset_id == asset_id,
                            AIReport.created_at >= cooldown_cutoff,
                        )
                        .limit(1)
                    )
                    if existing_report_result.scalar_one_or_none() is not None:
                        logger.info("%s 오늘 리포트 이미 존재 - 건너뜀", ticker)
                        continue

                    logger.info("%s 리포트 생성 시작", ticker)
                    await generate_report_for_ticker(ticker, db_session)
                    generated_count += 1
                    logger.info("%s 리포트 생성 완료", ticker)

                    # Rate-limit protection between LLM calls.
                    await asyncio.sleep(10)
                except ReportReadinessError as exc:
                    await db_session.rollback()
                    logger.error(
                        "%s report generation failed (failure_type=readiness_blocked, missing_required=%s, blocking_reasons=%s)",
                        ticker,
                        exc.metadata.get("missing_required_facts", []),
                        (exc.metadata.get("readiness") or {}).get("blocking_reasons", []),
                        exc_info=True,
                    )
                except ReportQualityError as exc:
                    await db_session.rollback()
                    logger.error(
                        "%s report generation failed (failure_type=quality_failed, revision_count=%s, feedback=%s)",
                        ticker,
                        exc.revision_count,
                        exc.feedback,
                        exc_info=True,
                    )
                except ValueError as exc:
                    await db_session.rollback()
                    logger.error(
                        "%s report generation failed (failure_type=provider_unavailable, error=%s)",
                        ticker,
                        exc,
                        exc_info=True,
                    )
                except Exception as exc:
                    await db_session.rollback()
                    logger.error("%s 리포트 실패: %s", ticker, exc, exc_info=True)

        logger.info("AI 리포트 생성 종료")
    except Exception as exc:
        logger.error(f"리포트 생성 중 에러 발생: {exc}", exc_info=True)

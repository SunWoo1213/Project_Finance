from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from ..core.cache import market_cache
from ..core.config import settings
try:
    from app.services.macro_service import fetch_commodity_data, fetch_kr_bond_data, fetch_us_bond_data
    from app.services.price_providers import (
        fetch_latest_provider_context,
        fetch_market_news_items,
        fetch_market_snapshot,
    )
except ModuleNotFoundError:
    from .macro_service import fetch_commodity_data, fetch_kr_bond_data, fetch_us_bond_data
    from .price_providers import fetch_latest_provider_context, fetch_market_news_items, fetch_market_snapshot

INDICES = {
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
}

BONDS = {
    "US 3M Treasury": "DGS3MO",
    "US 10Y Treasury": "DGS10",
}

KR_BONDS = {
    "KR 1Y Treasury": "KTB_1Y",
    "KR 10Y Treasury": "KTB_10Y",
    "KR 30Y Treasury": "KTB_30Y",
}

COMMODITIES = {
    "Gold": "XAU",
    "Silver": "XAG",
}

COMMODITIES_NEWS_SYMBOLS = {
    # Use commodity tickers as labels so report lookup by ticker works (XAU/XAG).
    "XAU": "GC=F",
    "XAG": "SI=F",
}

FX = {
    "USDKRW": "KRW=X",
}

CRYPTOS = {
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
}

US_TOP10 = {
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "NVDA": "NVDA",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
    "META": "META",
    "BRK-B": "BRK-B",
    "LLY": "LLY",
    "AVGO": "AVGO",
    "TSLA": "TSLA",
}

KR_TOP10 = {
    "Samsung Electronics": "005930.KS",
    "SK Hynix": "000660.KS",
    "LG Energy Solution": "373220.KS",
    "Samsung Biologics": "207940.KS",
    "Hyundai Motor": "005380.KS",
    "Kia": "000270.KS",
    "Celltrion": "068270.KS",
    "POSCO Holdings": "005490.KS",
    "NAVER": "035420.KS",
    "KB Financial Group": "105560.KS",
}

ALL_ASSETS = {
    **INDICES,
    **BONDS,
    **KR_BONDS,
    **COMMODITIES,
    **FX,
    **US_TOP10,
    **KR_TOP10,
    **CRYPTOS,
}


def _normalize_payload(
    current_price: float,
    change_percent: float,
    history_prices: list[float],
    market_cap: float = 0,
) -> dict[str, Any]:
    return {
        "currentPrice": round(float(current_price), 6),
        "changePercent": round(float(change_percent), 6),
        "history_prices": [round(float(v), 6) for v in history_prices],
        "marketCap": float(market_cap or 0),
    }


def _coerce_normalized_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    current_price = payload.get("currentPrice", payload.get("price", 0))
    change_percent = payload.get("changePercent", payload.get("change_pct", 0))
    history_prices = payload.get("history_prices", [])
    market_cap = payload.get("marketCap", 0)

    if not isinstance(history_prices, list):
        history_prices = []

    safe_history: list[float] = []
    for value in history_prices:
        try:
            safe_history.append(float(value))
        except (TypeError, ValueError):
            continue

    return {
        "currentPrice": float(current_price or 0),
        "changePercent": float(change_percent or 0),
        "history_prices": safe_history,
        "marketCap": float(market_cap or 0),
    }


def _to_frontend_shape(normalized: dict[str, Any]) -> dict[str, Any]:
    # Keep backward-compatible keys while exposing normalized keys.
    return {
        "price": normalized["currentPrice"],
        "change_pct": normalized["changePercent"],
        "history_prices": normalized["history_prices"],
        "marketCap": normalized["marketCap"],
        "currentPrice": normalized["currentPrice"],
        "changePercent": normalized["changePercent"],
    }


async def fetch_asset_data(ticker: str, category: str) -> dict[str, Any]:
    if category == "COMMODITY":
        raw = await fetch_commodity_data(ticker)
    elif category == "KR_BOND":
        raw = await fetch_kr_bond_data(ticker)
    elif category == "US_BOND":
        raw = await fetch_us_bond_data(ticker)
    else:
        raw = await fetch_market_snapshot(ticker, category)

    return _coerce_normalized_payload(raw)


def _build_asset_group(raw: dict[str, str], category: str) -> dict[str, dict[str, str]]:
    return {label: {"ticker": ticker, "category": category} for label, ticker in raw.items()}


MACRO_ASSETS = {
    **_build_asset_group(INDICES, "INDEX"),
    **_build_asset_group(FX, "FX"),
}
US_TOP10_ASSETS = _build_asset_group(US_TOP10, "STOCK_US")
KR_TOP10_ASSETS = _build_asset_group(KR_TOP10, "STOCK_KR")
BOND_ASSETS = {
    **_build_asset_group(BONDS, "US_BOND"),
    **_build_asset_group(KR_BONDS, "KR_BOND"),
}
COMMODITY_ASSETS = _build_asset_group(COMMODITIES, "COMMODITY")
CRYPTO_ASSETS = _build_asset_group(CRYPTOS, "CRYPTO")

NEWS_ASSETS = {
    **INDICES,
    **US_TOP10,
    **KR_TOP10,
    **CRYPTOS,
    **COMMODITIES_NEWS_SYMBOLS,
}

def _latest_context_ttl_seconds() -> int:
    # Configurable via MARKET_LATEST_CONTEXT_TTL_MINUTES; read at call time so
    # the cadence reflects the current environment without code changes.
    return settings.MARKET_LATEST_CONTEXT_TTL_MINUTES * 60


LATEST_CONTEXT_FORCE_REFRESH_COOLDOWN_SECONDS = 300


def _resolve_provider_news_symbol(ticker: str) -> str:
    normalized = (ticker or "").strip().upper()
    if normalized == "XAU":
        return "GC=F"
    if normalized == "XAG":
        return "SI=F"
    return ticker


def _is_latest_context_fresh(payload: dict[str, Any] | None, now: datetime) -> bool:
    if not payload:
        return False
    fetched_at_raw = payload.get("fetched_at")
    if not fetched_at_raw:
        return False
    try:
        fetched_at = datetime.fromisoformat(str(fetched_at_raw))
    except ValueError:
        return False
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return (now - fetched_at).total_seconds() < _latest_context_ttl_seconds()


def _is_latest_context_force_refresh_cooldown(payload: dict[str, Any] | None, now: datetime) -> bool:
    if not payload:
        return False
    fetched_at_raw = payload.get("fetched_at")
    if not fetched_at_raw:
        return False
    try:
        fetched_at = datetime.fromisoformat(str(fetched_at_raw))
    except ValueError:
        return False
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return (now - fetched_at).total_seconds() < LATEST_CONTEXT_FORCE_REFRESH_COOLDOWN_SECONDS


async def fetch_latest_asset_context(ticker: str, *, force_refresh: bool = False) -> dict[str, Any]:
    asset_ticker = (ticker or "").strip()
    now = datetime.now(timezone.utc)
    cache_bucket = market_cache.setdefault("latest_context", {})
    cached = cache_bucket.get(asset_ticker)
    if not force_refresh and _is_latest_context_fresh(cached, now):
        return cached
    if force_refresh and _is_latest_context_force_refresh_cooldown(cached, now):
        return cached

    symbol = _resolve_provider_news_symbol(asset_ticker)
    try:
        fetched = await asyncio.wait_for(
            fetch_latest_provider_context(symbol),
            timeout=8,
        )
        source_status = "fresh"
    except Exception as exc:
        fetched = {"news": [], "events": []}
        source_status = f"failed: {exc}"

    payload = {
        "ticker": asset_ticker,
        "symbol": symbol,
        "fetched_at": now.isoformat(),
        "ttl_seconds": _latest_context_ttl_seconds(),
        "source": "multi-provider",
        "source_status": source_status,
        "news": fetched.get("news", []),
        "events": fetched.get("events", []),
    }
    cache_bucket[asset_ticker] = payload
    market_cache.setdefault("last_updated", {}).setdefault("latest_context", {})[asset_ticker] = now.isoformat()
    return payload


async def _collect_prices_group(
    group_name: str, assets: dict[str, dict[str, str]]
) -> tuple[str, dict[str, Any]]:
    results: dict[str, Any] = {}

    async def collect_one(label: str, payload: dict[str, str]) -> None:
        ticker = payload["ticker"]
        category = payload["category"]
        try:
            normalized = await asyncio.wait_for(fetch_asset_data(ticker, category), timeout=15)
            results[label] = {"symbol": ticker, **_to_frontend_shape(normalized)}
        except Exception as exc:
            print(f"[update_prices_task] {label}({ticker}, {category}) failed: {exc}")

    await asyncio.gather(*(collect_one(label, payload) for label, payload in assets.items()))
    return group_name, results


async def _collect_news_group(group_name: str, tickers: dict[str, str]) -> tuple[str, dict[str, Any]]:
    results: dict[str, Any] = {}

    async def collect_one(label: str, symbol: str) -> None:
        try:
            news_data = await asyncio.wait_for(fetch_market_news_items(symbol), timeout=8)
            results[label] = {"symbol": symbol, "items": news_data}
        except Exception as exc:
            print(f"[update_news_task] {label}({symbol}) failed: {exc}")

    await asyncio.gather(*(collect_one(label, symbol) for label, symbol in tickers.items()))
    return group_name, results


async def update_prices_task() -> None:
    grouped = await asyncio.gather(
        _collect_prices_group("macro", MACRO_ASSETS),
        _collect_prices_group("us_top10", US_TOP10_ASSETS),
        _collect_prices_group("kr_top10", KR_TOP10_ASSETS),
        _collect_prices_group("bonds", BOND_ASSETS),
        _collect_prices_group("commodities", COMMODITY_ASSETS),
        _collect_prices_group("cryptos", CRYPTO_ASSETS),
    )
    market_cache["prices"] = {group_name: data for group_name, data in grouped}
    market_cache["last_updated"]["prices"] = datetime.now(timezone.utc).isoformat()
    print("[update_prices_task] cache updated")


async def update_news_task() -> None:
    grouped = await asyncio.gather(
        _collect_news_group("macro", INDICES),
        _collect_news_group("us_top10", US_TOP10),
        _collect_news_group("kr_top10", KR_TOP10),
        _collect_news_group("cryptos", CRYPTOS),
        _collect_news_group("commodities", COMMODITIES_NEWS_SYMBOLS),
    )
    market_cache["news"] = {group_name: data for group_name, data in grouped}
    market_cache["last_updated"]["news"] = datetime.now(timezone.utc).isoformat()
    print("[update_news_task] cache updated")

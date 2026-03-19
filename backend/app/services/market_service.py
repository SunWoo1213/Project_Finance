from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from ..core.cache import market_cache
try:
    from app.services.macro_service import fetch_commodity_data, fetch_kr_bond_data, fetch_us_bond_data
except ModuleNotFoundError:
    from .macro_service import fetch_commodity_data, fetch_kr_bond_data, fetch_us_bond_data

INDICES = {
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
}

BONDS = {
    "US 2M Treasury": "DGS2MO",
    "US 1Y Treasury": "DGS1",
    "US 10Y Treasury": "DGS10",
    "US 30Y Treasury": "DGS30",
}

KR_BONDS = {
    "KR 1Y Treasury": "KTB_1Y",
    "KR 3Y Treasury": "KTB_3Y",
    "KR 5Y Treasury": "KTB_5Y",
    "KR 10Y Treasury": "KTB_10Y",
    "KR 20Y Treasury": "KTB_20Y",
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


def _fetch_price_sync(symbol: str) -> dict[str, Any]:
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    history = ticker.history(period="1mo", interval="1d")
    if history.empty:
        raise ValueError(f"No price history for {symbol}")

    current_price = float(history["Close"].iloc[-1])
    prev_close = float(history["Close"].iloc[-2]) if len(history) >= 2 else current_price
    change_pct = 0.0 if prev_close == 0 else ((current_price - prev_close) / prev_close) * 100
    history_prices = [float(p) for p in history["Close"]]
    market_cap = float(info.get("marketCap", 0) or 0)
    return _normalize_payload(current_price, change_pct, history_prices, market_cap)


def _fetch_news_sync(symbol: str, limit: int = 5) -> list[dict[str, str]]:
    ticker = yf.Ticker(symbol)
    raw_news = ticker.news or []
    parsed: list[dict[str, str]] = []

    for item in raw_news[:limit]:
        title = item.get("title") or ""
        link = item.get("link") or item.get("url") or ""
        source = item.get("publisher") or item.get("provider") or "unknown"
        if not title and not link:
            continue
        parsed.append({"title": title, "link": link, "source": source})
    return parsed


async def fetch_asset_data(ticker: str, category: str) -> dict[str, Any]:
    async def fetch_yfinance_data(symbol: str) -> dict[str, Any]:
        return await asyncio.to_thread(_fetch_price_sync, symbol)

    if category == "COMMODITY":
        raw = await fetch_commodity_data(ticker)
    elif category == "KR_BOND":
        raw = await fetch_kr_bond_data(ticker)
    elif category == "US_BOND":
        raw = await fetch_us_bond_data(ticker)
    else:
        raw = await fetch_yfinance_data(ticker)

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
            news_data = await asyncio.wait_for(asyncio.to_thread(_fetch_news_sync, symbol), timeout=8)
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

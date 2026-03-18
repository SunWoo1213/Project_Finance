import asyncio
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from ..core.cache import market_cache

MACRO_TICKERS = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "S&P500": "^GSPC",
    "NASDAQ100": "^NDX",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "USDKRW": "KRW=X",
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
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "현대차": "005380.KS",
    "기아": "000270.KS",
    "셀트리온": "068270.KS",
    "POSCO홀딩스": "005490.KS",
    "NAVER": "035420.KS",
    "KB금융": "105560.KS",
}


def _fetch_price_sync(symbol: str) -> dict[str, float]:
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="2d", interval="1d")
    if history.empty:
        raise ValueError(f"No price history for {symbol}")

    current_price = float(history["Close"].iloc[-1])
    if len(history) >= 2:
        prev_close = float(history["Close"].iloc[-2])
    else:
        prev_close = current_price

    change_pct = 0.0 if prev_close == 0 else ((current_price - prev_close) / prev_close) * 100
    return {"price": current_price, "change_pct": round(change_pct, 4)}


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


async def _collect_prices_group(group_name: str, tickers: dict[str, str]) -> tuple[str, dict[str, Any]]:
    results: dict[str, Any] = {}

    async def collect_one(label: str, symbol: str) -> None:
        try:
            price_data = await asyncio.wait_for(asyncio.to_thread(_fetch_price_sync, symbol), timeout=8)
            results[label] = {"symbol": symbol, **price_data}
        except Exception as exc:
            print(f"[update_prices_task] {label}({symbol}) failed: {exc}")

    await asyncio.gather(*(collect_one(label, symbol) for label, symbol in tickers.items()))
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
        _collect_prices_group("macro", MACRO_TICKERS),
        _collect_prices_group("us_top10", US_TOP10),
        _collect_prices_group("kr_top10", KR_TOP10),
    )
    market_cache["prices"] = {group_name: data for group_name, data in grouped}
    market_cache["last_updated"]["prices"] = datetime.now(timezone.utc).isoformat()
    print("[update_prices_task] cache updated")


async def update_news_task() -> None:
    grouped = await asyncio.gather(
        _collect_news_group("macro", MACRO_TICKERS),
        _collect_news_group("us_top10", US_TOP10),
        _collect_news_group("kr_top10", KR_TOP10),
    )
    market_cache["news"] = {group_name: data for group_name, data in grouped}
    market_cache["last_updated"]["news"] = datetime.now(timezone.utc).isoformat()
    print("[update_news_task] cache updated")

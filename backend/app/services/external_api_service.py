from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

import httpx

from ..core.config import settings

FMP_API_KEY = os.getenv("FMP_API_KEY") or getattr(settings, "FMP_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY") or getattr(settings, "FINNHUB_API_KEY", "")

COINGECKO_TICKER_MAP = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "SOL-USD": "solana",
    "XRP-USD": "ripple",
    "DOGE-USD": "dogecoin",
}


async def fetch_fmp_financials(ticker: str) -> str:
    if not ticker or not FMP_API_KEY:
        return ""

    url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list) or not payload:
            return ""

        row: dict[str, Any] = payload[0] or {}
        industry = row.get("industry", "-")
        beta = row.get("beta", "-")
        mkt_cap = row.get("mktCap", "-")
        price = row.get("price", "-")
        vol_avg = row.get("volAvg", "-")
        description = row.get("description", "-")

        return (
            f"FMP 요약: [산업: {industry}, 베타: {beta}, 시가총액: {mkt_cap}, "
            f"현재가: {price}, 평균거래량: {vol_avg}, 기업설명: {description}]"
        )
    except Exception:
        return ""


async def fetch_finnhub_news(ticker: str) -> str:
    if not ticker or not FINNHUB_API_KEY:
        return ""

    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    url = (
        "https://finnhub.io/api/v1/company-news"
        f"?symbol={ticker}&from={week_ago.isoformat()}&to={today.isoformat()}&token={FINNHUB_API_KEY}"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list) or not payload:
            return ""

        lines: list[str] = []
        for idx, item in enumerate(payload[:5], start=1):
            headline = (item or {}).get("headline", "").strip()
            summary = (item or {}).get("summary", "").strip()
            if not headline and not summary:
                continue
            lines.append(f"뉴스 {idx}: [{headline}] - [{summary}]")

        return "\n".join(lines) if lines else ""
    except Exception:
        return ""


async def fetch_coingecko_data(ticker: str) -> str:
    if not ticker:
        return ""

    coin_id = COINGECKO_TICKER_MAP.get(str(ticker).upper())
    if not coin_id:
        return ""

    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={coin_id}&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        coin_data = (payload or {}).get(coin_id, {})
        if not isinstance(coin_data, dict) or not coin_data:
            return ""

        price = coin_data.get("usd", "-")
        vol_24h = coin_data.get("usd_24h_vol", "-")
        change_24h = coin_data.get("usd_24h_change", "-")

        return f"CoinGecko 요약: [가격: {price}, 24H거래량: {vol_24h}, 24H변동폭: {change_24h}%]"
    except Exception:
        return ""

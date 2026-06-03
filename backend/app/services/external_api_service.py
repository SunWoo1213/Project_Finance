from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx

from ..core.config import settings

FMP_API_KEY = settings.FMP_API_KEY or ""
FINNHUB_API_KEY = settings.FINNHUB_API_KEY or ""
COINGECKO_DEMO_API_KEY = settings.COINGECKO_DEMO_API_KEY or ""

COINGECKO_TICKER_MAP = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "SOL-USD": "solana",
    "XRP-USD": "ripple",
    "DOGE-USD": "dogecoin",
}


def _empty_provider_payload(provider: str, status: str, reason: str = "") -> dict[str, Any]:
    return {
        "provider": provider,
        "status": status,
        "as_of": datetime.now().isoformat(),
        "items": [],
        "limitations": [reason] if reason else [],
    }


def format_provider_facts(payload: dict[str, Any]) -> str:
    if not payload or payload.get("status") != "fresh":
        limitations = "; ".join(payload.get("limitations", [])) if payload else "no payload"
        return f"{payload.get('provider', 'provider')} 데이터 없음: {limitations}"

    lines = []
    for item in payload.get("items", []):
        label = item.get("label") or item.get("title") or "fact"
        value = item.get("value") or item.get("summary") or ""
        source = item.get("source", payload.get("provider", "unknown"))
        as_of = item.get("as_of", payload.get("as_of", ""))
        lines.append(f"- {label}: {value} (source={source}, as_of={as_of})")
    return "\n".join(lines)


async def fetch_fmp_financials_structured(ticker: str) -> dict[str, Any]:
    if not ticker or not FMP_API_KEY:
        return _empty_provider_payload("FMP", "missing", "FMP_API_KEY가 없어 FMP 재무 데이터를 수집하지 않았습니다.")

    url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list) or not payload:
            return _empty_provider_payload("FMP", "empty", "FMP profile 응답이 비어 있습니다.")

        row: dict[str, Any] = payload[0] or {}
        as_of = datetime.now().isoformat()
        items = []
        field_map = {
            "industry": "산업",
            "sector": "섹터",
            "beta": "베타",
            "mktCap": "시가총액",
            "price": "현재가",
            "volAvg": "평균거래량",
        }
        for raw_key, label in field_map.items():
            value = row.get(raw_key)
            if value in (None, ""):
                continue
            items.append(
                {
                    "label": label,
                    "value": value,
                    "as_of": as_of,
                    "source": "FMP profile",
                    "url": "https://financialmodelingprep.com/developer/docs/",
                    "confidence": "medium",
                }
            )
        description = row.get("description")
        if description:
            items.append(
                {
                    "label": "기업설명",
                    "value": str(description)[:600],
                    "as_of": as_of,
                    "source": "FMP profile",
                    "url": "https://financialmodelingprep.com/developer/docs/",
                    "confidence": "medium",
                }
            )

        return {
            "provider": "FMP",
            "status": "fresh" if items else "empty",
            "as_of": as_of,
            "items": items,
            "limitations": [] if items else ["FMP profile에서 사용 가능한 재무 항목이 없었습니다."],
        }
    except Exception as exc:
        return _empty_provider_payload("FMP", "failed", f"FMP 재무 데이터 수집 실패: {exc}")


async def fetch_fmp_financials(ticker: str) -> str:
    payload = await fetch_fmp_financials_structured(ticker)
    return format_provider_facts(payload) if payload.get("status") == "fresh" else ""


async def fetch_finnhub_news_structured(ticker: str) -> dict[str, Any]:
    if not ticker or not FINNHUB_API_KEY:
        return _empty_provider_payload("Finnhub", "missing", "FINNHUB_API_KEY가 없어 Finnhub 뉴스를 수집하지 않았습니다.")

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
            return _empty_provider_payload("Finnhub", "empty", "최근 1주일 Finnhub company-news 응답이 비어 있습니다.")

        items: list[dict[str, Any]] = []
        for item in payload[:5]:
            item = item or {}
            headline = str(item.get("headline") or "").strip()
            summary = str(item.get("summary") or "").strip()
            if not headline and not summary:
                continue
            published_at = item.get("datetime")
            as_of = datetime.fromtimestamp(published_at).isoformat() if published_at else datetime.now().isoformat()
            items.append(
                {
                    "title": headline,
                    "summary": summary,
                    "as_of": as_of,
                    "source": item.get("source") or "Finnhub company-news",
                    "url": item.get("url") or "",
                    "confidence": "medium",
                }
            )

        return {
            "provider": "Finnhub",
            "status": "fresh" if items else "empty",
            "as_of": datetime.now().isoformat(),
            "items": items,
            "limitations": [] if items else ["Finnhub 뉴스 항목에 제목/요약이 없습니다."],
        }
    except Exception as exc:
        return _empty_provider_payload("Finnhub", "failed", f"Finnhub 뉴스 수집 실패: {exc}")


async def fetch_finnhub_news(ticker: str) -> str:
    payload = await fetch_finnhub_news_structured(ticker)
    if payload.get("status") != "fresh":
        return ""
    lines: list[str] = []
    for idx, item in enumerate(payload.get("items", [])[:5], start=1):
        headline = (item or {}).get("title", "").strip()
        summary = (item or {}).get("summary", "").strip()
        if not headline and not summary:
            continue
        lines.append(f"뉴스 {idx}: [{headline}] - [{summary}]")

    return "\n".join(lines) if lines else ""


async def fetch_coingecko_data_structured(ticker: str) -> dict[str, Any]:
    if not ticker:
        return _empty_provider_payload("CoinGecko", "missing", "ticker가 없어 CoinGecko 데이터를 수집하지 않았습니다.")
    if not COINGECKO_DEMO_API_KEY:
        return _empty_provider_payload(
            "CoinGecko",
            "missing",
            "COINGECKO_DEMO_API_KEY가 없어 CoinGecko 데이터를 수집하지 않았습니다.",
        )

    coin_id = COINGECKO_TICKER_MAP.get(str(ticker).upper())
    if not coin_id:
        return _empty_provider_payload("CoinGecko", "unsupported", f"{ticker}는 CoinGecko 매핑에 없습니다.")

    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={coin_id}&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers={"x-cg-demo-api-key": COINGECKO_DEMO_API_KEY})
            response.raise_for_status()
            payload = response.json()

        coin_data = (payload or {}).get(coin_id, {})
        if not isinstance(coin_data, dict) or not coin_data:
            return _empty_provider_payload("CoinGecko", "empty", "CoinGecko simple price 응답이 비어 있습니다.")

        as_of = datetime.now().isoformat()
        items = []
        field_map = {
            "usd": "가격",
            "usd_24h_vol": "24H 거래량",
            "usd_24h_change": "24H 변동률",
        }
        for raw_key, label in field_map.items():
            value = coin_data.get(raw_key)
            if value in (None, ""):
                continue
            items.append(
                {
                    "label": label,
                    "value": value,
                    "as_of": as_of,
                    "source": "CoinGecko simple price",
                    "url": "https://www.coingecko.com/en/api",
                    "confidence": "medium",
                }
            )
        return {
            "provider": "CoinGecko",
            "status": "fresh" if items else "empty",
            "as_of": as_of,
            "items": items,
            "limitations": [] if items else ["CoinGecko 응답에 사용 가능한 가격 항목이 없습니다."],
        }
    except Exception as exc:
        return _empty_provider_payload("CoinGecko", "failed", f"CoinGecko 데이터 수집 실패: {exc}")


async def fetch_coingecko_data(ticker: str) -> str:
    payload = await fetch_coingecko_data_structured(ticker)
    if payload.get("status") != "fresh":
        return ""
    values = {item.get("label"): item.get("value") for item in payload.get("items", [])}
    return (
        f"CoinGecko 요약: [가격: {values.get('가격', '-')}, "
        f"24H거래량: {values.get('24H 거래량', '-')}, "
        f"24H변동폭: {values.get('24H 변동률', '-')}%]"
    )

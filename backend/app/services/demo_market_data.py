from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..core.config import settings

DEFAULT_LIVE_TICKERS = "DGS10,XAU,BTC-USD,NVDA,005930.KS"
MOCK_PROVIDER = "demo_mock"

_BASE_VALUES = {
    "^GSPC": 5310.24,
    "^NDX": 19042.11,
    "^KS11": 2745.31,
    "^KQ11": 842.77,
    "KRW=X": 1378.2,
    "DGS3MO": 5.31,
    "DGS1": 4.86,
    "DGS2MO": 5.36,
    "DGS30": 4.58,
    "KTB_1Y": 3.22,
    "KTB_10Y": 3.48,
    "KTB_30Y": 3.39,
    "XAG": 30.4,
    "ETH-USD": 3680.0,
}


def _normalize_ticker(ticker: str) -> str:
    return (ticker or "").strip().upper()


def _configured_live_tickers() -> set[str] | None:
    raw = (settings.MARKET_LIVE_TICKERS or DEFAULT_LIVE_TICKERS).strip()
    if raw == "*":
        return None
    return {_normalize_ticker(part) for part in raw.split(",") if part.strip()}


def is_live_market_ticker(ticker: str) -> bool:
    live_tickers = _configured_live_tickers()
    if live_tickers is None:
        return True
    return _normalize_ticker(ticker) in live_tickers


def _stable_seed(ticker: str) -> int:
    normalized = _normalize_ticker(ticker)
    return sum((index + 1) * ord(char) for index, char in enumerate(normalized))


def _mock_base_value(ticker: str, category: str | None = None) -> float:
    normalized = _normalize_ticker(ticker)
    if normalized in _BASE_VALUES:
        return _BASE_VALUES[normalized]
    if normalized.endswith(".KS"):
        return float(45000 + (_stable_seed(normalized) % 220000))
    category = (category or "").strip().upper()
    if category in {"US_BOND", "KR_BOND"} or normalized.startswith(("DGS", "KTB_")):
        return round(2.5 + (_stable_seed(normalized) % 240) / 100, 4)
    if category == "CRYPTO":
        return float(1000 + (_stable_seed(normalized) % 70000))
    if category == "COMMODITY":
        return float(20 + (_stable_seed(normalized) % 4000))
    return float(80 + (_stable_seed(normalized) % 420))


def _mock_change_percent(ticker: str) -> float:
    seed = _stable_seed(ticker)
    return round(((seed % 280) - 140) / 100, 6)


def mock_history_points(ticker: str, period: str = "1mo", category: str | None = None) -> list[dict[str, Any]]:
    days = {
        "1d": 7,
        "1mo": 30,
        "1y": 365,
        "5y": 1825,
    }.get(period, 30)
    today = datetime.now(timezone.utc).date()
    base = _mock_base_value(ticker, category)
    seed = _stable_seed(ticker)
    change = _mock_change_percent(ticker)
    slope = change / max(days - 1, 1) / 100
    points: list[dict[str, Any]] = []

    for index in range(days):
        wave = (((seed + index * 17) % 21) - 10) / 1000
        value = base * (1 + slope * index + wave)
        points.append(
            {
                "date": (today - timedelta(days=days - 1 - index)).isoformat(),
                "value": round(value, 6),
            }
        )
    return points


def mock_price_payload(ticker: str, category: str | None = None) -> dict[str, Any]:
    points = mock_history_points(ticker, "1mo", category)
    current_price = points[-1]["value"] if points else _mock_base_value(ticker, category)
    previous_price = points[-2]["value"] if len(points) >= 2 else current_price
    change_percent = 0.0 if previous_price == 0 else ((current_price - previous_price) / previous_price) * 100
    return {
        "currentPrice": round(float(current_price), 6),
        "changePercent": round(float(change_percent), 6),
        "history_prices": [point["value"] for point in points],
        "marketCap": 0.0,
        "provider_meta": mock_provider_meta(ticker),
    }


def _history_unit(ticker: str) -> str:
    normalized = _normalize_ticker(ticker)
    if normalized.startswith(("DGS", "KTB_")):
        return "%"
    if normalized == "KRW=X" or normalized.endswith(".KS") or normalized.startswith("^K"):
        return "KRW"
    return "USD"


def _history_series_type(ticker: str) -> str:
    normalized = _normalize_ticker(ticker)
    return "yield" if normalized.startswith(("DGS", "KTB_")) else "price"


def mock_provider_meta(ticker: str) -> dict[str, Any]:
    return {
        "provider": MOCK_PROVIDER,
        "freshness": "mock",
        "mode": "live_ticker_allowlist",
        "live_tickers": settings.MARKET_LIVE_TICKERS or DEFAULT_LIVE_TICKERS,
        "ticker": _normalize_ticker(ticker),
    }


def mock_history_payload(ticker: str, period: str = "1y", category: str | None = None) -> dict[str, Any]:
    normalized = _normalize_ticker(ticker)
    points = mock_history_points(normalized, period, category)
    return {
        "ticker": normalized,
        "series_type": _history_series_type(normalized),
        "unit": _history_unit(normalized),
        "points": points,
        "legacy": [
            {"date": point["date"], "close": point["value"], "value": point["value"]}
            for point in points
        ],
        "provider_meta": mock_provider_meta(normalized),
    }


def mock_news_items(ticker: str, limit: int = 5) -> list[dict[str, Any]]:
    normalized = _normalize_ticker(ticker)
    today = datetime.now(timezone.utc).date().isoformat()
    items = [
        {
            "title": f"{normalized} demo market update",
            "link": "",
            "source": MOCK_PROVIDER,
            "published_at": today,
            "summary": "Demo data is shown to reduce free-tier provider calls.",
            "type": "news",
        }
    ]
    return items[:limit]


def mock_latest_context(ticker: str, symbol: str | None = None, *, limit: int = 8) -> dict[str, Any]:
    asset_ticker = ticker or symbol or ""
    resolved_symbol = symbol or asset_ticker
    now = datetime.now(timezone.utc)
    return {
        "ticker": asset_ticker,
        "symbol": resolved_symbol,
        "fetched_at": now.isoformat(),
        "ttl_seconds": settings.MARKET_LATEST_CONTEXT_TTL_MINUTES * 60,
        "source": MOCK_PROVIDER,
        "source_status": "mocked_by_market_live_tickers",
        "news": mock_news_items(resolved_symbol, limit=limit),
        "events": [],
        "provider_meta": mock_provider_meta(resolved_symbol),
    }

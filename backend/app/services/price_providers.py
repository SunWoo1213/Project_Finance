from __future__ import annotations

import csv
import html
import io
import logging
import re
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any
from urllib.parse import quote

import httpx

from ..core.config import settings
from ..core.log_sanitizer import redact_secrets

logger = logging.getLogger(__name__)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
STOOQ_DAILY_CSV_URL = "https://stooq.com/q/d/l/"
EXCHANGE_RATE_OPEN_URL = "https://open.er-api.com/v6/latest/USD"
DATA_GO_STOCK_URL = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
DATA_GO_INDEX_URL = "https://apis.data.go.kr/1160100/service/GetMarketIndexInfoService/getStockMarketIndex"
NAVER_NEWS_URL = "https://search.naver.com/search.naver"

FAILED_CALL_TTL_SECONDS = 300
SNAPSHOT_CACHE_TTL_SECONDS = 300
PROFILE_CACHE_TTL_SECONDS = 12 * 60 * 60
HISTORY_CACHE_TTL_SECONDS = 12 * 60 * 60
FX_CACHE_TTL_SECONDS = 24 * 60 * 60
DATA_GO_CACHE_TTL_SECONDS = 30 * 60

DEFAULT_RESPONSE = {
    "currentPrice": 0.0,
    "changePercent": 0.0,
    "history_prices": [],
    "marketCap": 0.0,
}

COINGECKO_TICKER_MAP = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
}

STOOQ_SYMBOLS = {
    "^GSPC": "^spx",
    "^NDX": "^ndx",
    "AAPL": "aapl.us",
    "MSFT": "msft.us",
    "NVDA": "nvda.us",
    "GOOGL": "googl.us",
    "AMZN": "amzn.us",
    "META": "meta.us",
    "BRK-B": "brk-b.us",
    "LLY": "lly.us",
    "AVGO": "avgo.us",
    "TSLA": "tsla.us",
    "XAU": "xauusd",
    "GC=F": "xauusd",
    "XAG": "xagusd",
    "SI=F": "xagusd",
    "KRW=X": "usdkrw",
}

US_STOCK_SYMBOLS = {
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "AMZN",
    "META",
    "BRK-B",
    "LLY",
    "AVGO",
    "TSLA",
}

# data.go.kr getStockMarketIndex matches idxNm by the Korean index name; the
# English forms ("KOSPI"/"KOSDAQ") return totalCount=0 (empty). Keys stay as the
# internal yfinance-style tickers used for membership checks.
KR_INDEX_NAMES = {
    "^KS11": "코스피",
    "^KQ11": "코스닥",
}

_provider_semaphores: dict[str, Any] = {}
_failed_call_cache: dict[str, float] = {}
_snapshot_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_profile_cache: dict[str, tuple[float, float]] = {}
_history_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _provider_concurrency(provider: str) -> int:
    # Most providers stay serialized (Semaphore(1)) to avoid rate-limit/IP
    # throttling. data.go.kr is slow (~20s/call) so it gets a small, configurable
    # concurrency bump to let its serialized queue drain across cycles.
    if provider == "data_go_kr":
        return max(1, settings.DATA_GO_KR_MAX_CONCURRENCY)
    return 1


def _provider_semaphore(provider: str):
    import asyncio

    semaphore = _provider_semaphores.get(provider)
    if semaphore is None:
        semaphore = asyncio.Semaphore(_provider_concurrency(provider))
        _provider_semaphores[provider] = semaphore
    return semaphore


def _cache_get(cache: dict[str, tuple[float, Any]], key: str, ttl_seconds: int) -> Any | None:
    cached = cache.get(key)
    if not cached:
        return None
    cached_at, payload = cached
    if monotonic() - cached_at < ttl_seconds:
        return payload
    cache.pop(key, None)
    return None


def _cache_set(cache: dict[str, tuple[float, Any]], key: str, payload: Any) -> Any:
    cache[key] = (monotonic(), payload)
    return payload


def _should_skip_failed_call(key: str) -> bool:
    failed_at = _failed_call_cache.get(key)
    if failed_at is None:
        return False
    if monotonic() - failed_at < FAILED_CALL_TTL_SECONDS:
        return True
    _failed_call_cache.pop(key, None)
    return False


def _mark_failed_call(key: str) -> None:
    _failed_call_cache[key] = monotonic()


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _normalize_history_values(history_prices: list[float], market_cap: float = 0.0) -> dict[str, Any]:
    if not history_prices:
        return dict(DEFAULT_RESPONSE)
    current_price = float(history_prices[-1])
    prev_price = float(history_prices[-2]) if len(history_prices) >= 2 else current_price
    change_percent = 0.0 if prev_price == 0 else ((current_price - prev_price) / prev_price) * 100
    return {
        "currentPrice": round(current_price, 6),
        "changePercent": round(change_percent, 6),
        "history_prices": [round(float(v), 6) for v in history_prices],
        "marketCap": float(market_cap or 0.0),
    }


def _normalize_points(points: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for point in points:
        raw_date = str(point.get("date") or "").strip()
        value = _safe_float(point.get("value", point.get("close")), default=float("nan"))
        if not raw_date or value != value:
            continue
        parsed.append({"date": raw_date, "value": value})
    parsed.sort(key=lambda item: item["date"])
    return parsed[-limit:] if limit else parsed


def _history_payload(ticker: str, points: list[dict[str, Any]], *, unit: str = "USD") -> dict[str, Any]:
    normalized_points = _normalize_points(points)
    return {
        "ticker": ticker,
        "series_type": "price",
        "unit": unit,
        "points": normalized_points,
        "legacy": [
            {"date": point["date"], "close": point["value"], "value": point["value"]}
            for point in normalized_points
        ],
    }


def _period_to_days(period: str) -> int:
    return {
        "1d": 30,
        "1mo": 30,
        "1y": 365,
        "5y": 1825,
    }.get(period, 365)


def _is_kr_stock(ticker: str) -> bool:
    return ticker.upper().endswith(".KS") and len(ticker.split(".", 1)[0]) == 6


def _kr_stock_code(ticker: str) -> str:
    return ticker.upper().split(".", 1)[0]


def _is_crypto(ticker: str) -> bool:
    return ticker.upper() in COINGECKO_TICKER_MAP


def _is_commodity(ticker: str) -> bool:
    return ticker.upper() in {"XAU", "XAG", "GC=F", "SI=F"}


def _finnhub_token() -> str:
    return settings.FINNHUB_API_KEY or ""


def _coingecko_key() -> str:
    return settings.COINGECKO_DEMO_API_KEY or ""


def _data_go_key() -> str:
    return settings.DATA_GO_KR_API_KEY or ""


def _stooq_key() -> str:
    return settings.STOOQ_API_KEY or ""


async def _get_json(
    provider: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> Any:
    request_key = f"{provider}:{url}:{params}"
    if _should_skip_failed_call(request_key):
        raise RuntimeError(f"{provider} cooldown active")

    async with _provider_semaphore(provider):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response.json()
        except Exception:
            _mark_failed_call(request_key)
            raise


async def _get_text(
    provider: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> str:
    request_key = f"{provider}:{url}:{params}"
    if _should_skip_failed_call(request_key):
        raise RuntimeError(f"{provider} cooldown active")

    async with _provider_semaphore(provider):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response.text
        except Exception:
            _mark_failed_call(request_key)
            raise


async def _fetch_finnhub_profile_market_cap(symbol: str) -> float:
    cache_key = f"finnhub_profile:{symbol}"
    cached = _cache_get(_profile_cache, cache_key, PROFILE_CACHE_TTL_SECONDS)
    if cached is not None:
        return float(cached)

    token = _finnhub_token()
    if not token:
        return 0.0

    payload = await _get_json(
        "finnhub",
        f"{FINNHUB_BASE_URL}/stock/profile2",
        params={"symbol": symbol, "token": token},
    )
    market_cap_millions = _safe_float((payload or {}).get("marketCapitalization"))
    market_cap = market_cap_millions * 1_000_000 if market_cap_millions else 0.0
    return _cache_set(_profile_cache, cache_key, market_cap)


async def _fetch_finnhub_stock_snapshot(symbol: str) -> dict[str, Any]:
    token = _finnhub_token()
    if not token:
        return dict(DEFAULT_RESPONSE)

    payload = await _get_json(
        "finnhub",
        f"{FINNHUB_BASE_URL}/quote",
        params={"symbol": symbol, "token": token},
    )
    current_price = _safe_float((payload or {}).get("c"))
    prev_close = _safe_float((payload or {}).get("pc"), default=current_price)
    change_percent = _safe_float((payload or {}).get("dp"))
    if change_percent == 0.0 and prev_close:
        change_percent = ((current_price - prev_close) / prev_close) * 100
    market_cap = await _fetch_finnhub_profile_market_cap(symbol)
    history = await fetch_stooq_history(symbol, "1mo")
    history_prices = [point["value"] for point in history.get("points", [])]
    if not history_prices and current_price:
        history_prices = [current_price]
    return {
        "currentPrice": round(current_price, 6),
        "changePercent": round(change_percent, 6),
        "history_prices": history_prices,
        "marketCap": market_cap,
    }


async def _fetch_coingecko_snapshot(ticker: str) -> dict[str, Any]:
    key = _coingecko_key()
    coin_id = COINGECKO_TICKER_MAP.get(ticker.upper())
    if not key or not coin_id:
        return dict(DEFAULT_RESPONSE)

    payload = await _get_json(
        "coingecko",
        f"{COINGECKO_BASE_URL}/simple/price",
        params={
            "ids": coin_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_market_cap": "true",
        },
        headers={"x-cg-demo-api-key": key},
    )
    coin_data = (payload or {}).get(coin_id, {})
    current_price = _safe_float(coin_data.get("usd"))
    change_percent = _safe_float(coin_data.get("usd_24h_change"))
    market_cap = _safe_float(coin_data.get("usd_market_cap"))
    history = await fetch_coingecko_history(ticker, "1mo")
    history_prices = [point["value"] for point in history.get("points", [])]
    if not history_prices and current_price:
        history_prices = [current_price]
    return {
        "currentPrice": round(current_price, 6),
        "changePercent": round(change_percent, 6),
        "history_prices": history_prices,
        "marketCap": market_cap,
    }


async def _fetch_fx_snapshot(ticker: str) -> dict[str, Any]:
    cached = _cache_get(_snapshot_cache, f"fx:{ticker}", FX_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    payload = await _get_json("exchange_rate_open", EXCHANGE_RATE_OPEN_URL, timeout=8.0)
    rates = (payload or {}).get("rates", {})
    current_price = _safe_float(rates.get("KRW"))

    # open.er-api는 현재 환율만 주고 전일 종가가 없어서 changePercent를 0으로 둘 수밖에
    # 없었다. finnhub 주식 스냅샷과 동일하게, stooq의 일별 USD/KRW 종가를 전일 종가로
    # 삼아 실제 등락폭을 계산한다. stooq 키가 없거나 데이터가 없으면 폴백한다.
    history = await fetch_stooq_history("KRW=X", "1mo")
    history_prices = [point["value"] for point in history.get("points", [])]

    if not current_price and history_prices:
        current_price = history_prices[-1]

    prev_close = history_prices[-1] if history_prices else 0.0
    change_percent = (
        ((current_price - prev_close) / prev_close) * 100
        if prev_close and current_price
        else 0.0
    )

    if not history_prices and current_price:
        history_prices = [current_price]

    result = {
        "currentPrice": round(current_price, 6),
        "changePercent": round(change_percent, 6),
        "history_prices": [round(float(v), 6) for v in history_prices],
        "marketCap": 0.0,
        "provider_meta": {
            "source": "open.er-api.com",
            "provider": (payload or {}).get("provider"),
            "as_of": (payload or {}).get("time_last_update_utc"),
            "change_source": "stooq" if prev_close else "none",
        },
    }
    return _cache_set(_snapshot_cache, f"fx:{ticker}", result)


def _parse_stooq_csv(text: str, limit: int | None = None) -> list[dict[str, Any]]:
    if not text or "Get your apikey" in text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    points: list[dict[str, Any]] = []
    for row in reader:
        date = str(row.get("Date") or "").strip()
        close = _safe_float(row.get("Close"), default=float("nan"))
        if not date or close != close:
            continue
        points.append({"date": date, "value": close})
    points.sort(key=lambda item: item["date"])
    return points[-limit:] if limit else points


async def fetch_stooq_history(ticker: str, period: str = "1y") -> dict[str, Any]:
    stooq_symbol = STOOQ_SYMBOLS.get(ticker.upper())
    key = _stooq_key()
    cache_key = f"stooq:{ticker.upper()}:{period}"
    cached = _cache_get(_history_cache, cache_key, HISTORY_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached
    if not stooq_symbol or not key:
        return _history_payload(ticker.upper(), [])

    text = await _get_text(
        "stooq",
        STOOQ_DAILY_CSV_URL,
        params={"s": stooq_symbol, "i": "d", "apikey": key},
        timeout=12.0,
    )
    points = _parse_stooq_csv(text, limit=_period_to_days(period))
    payload = _history_payload(ticker.upper(), points)
    if not points:
        _mark_failed_call(cache_key)
    return _cache_set(_history_cache, cache_key, payload)


async def _fetch_stooq_snapshot(ticker: str) -> dict[str, Any]:
    history = await fetch_stooq_history(ticker, "1mo")
    points = history.get("points", [])
    return _normalize_history_values([point["value"] for point in points])


def _extract_data_go_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    body = (((payload or {}).get("response") or {}).get("body") or {})
    items = (body.get("items") or {}).get("item", [])
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def _data_go_params(extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "serviceKey": _data_go_key(),
        "resultType": "json",
        "pageNo": 1,
        **extra,
    }


def _recent_basdt_window(days: int = 20) -> dict[str, str]:
    # Bound data.go.kr snapshot queries to a recent date window. A date-less
    # likeSrtnCd/idxNm query scans the full series and is slow/empty; a window
    # wide enough to cover KR market holidays returns the latest trading day fast.
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    return {"beginBasDt": start.strftime("%Y%m%d"), "endBasDt": end.strftime("%Y%m%d")}


async def _fetch_data_go_rows(url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    if not _data_go_key():
        return []
    payload = await _get_json(
        "data_go_kr",
        url,
        params=params,
        timeout=float(settings.DATA_GO_KR_FETCH_TIMEOUT_SECONDS),
    )
    return _extract_data_go_items(payload)


def _data_go_row_to_point(row: dict[str, Any]) -> dict[str, Any] | None:
    date = str(row.get("basDt") or "").strip()
    value = _safe_float(row.get("clpr"), default=float("nan"))
    if not date or value != value:
        return None
    if len(date) == 8 and date.isdigit():
        date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
    return {"date": date, "value": value}


async def fetch_data_go_stock_history(ticker: str, period: str = "1y") -> dict[str, Any]:
    code = _kr_stock_code(ticker)
    cache_key = f"data_go_stock:{code}:{period}"
    cached = _cache_get(_history_cache, cache_key, HISTORY_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=_period_to_days(period) + 10)
    rows = await _fetch_data_go_rows(
        DATA_GO_STOCK_URL,
        _data_go_params(
            {
                "numOfRows": max(30, min(2000, _period_to_days(period) + 20)),
                "beginBasDt": start.strftime("%Y%m%d"),
                "endBasDt": end.strftime("%Y%m%d"),
                "likeSrtnCd": code,
            }
        ),
    )
    points = [
        point for point in (_data_go_row_to_point(row) for row in rows)
        if point is not None
    ]
    payload = _history_payload(ticker.upper(), points[-_period_to_days(period):], unit="KRW")
    if not points:
        _mark_failed_call(cache_key)
    return _cache_set(_history_cache, cache_key, payload)


async def fetch_data_go_index_history(ticker: str, period: str = "1y") -> dict[str, Any]:
    index_name = KR_INDEX_NAMES.get(ticker.upper())
    cache_key = f"data_go_index:{ticker.upper()}:{period}"
    cached = _cache_get(_history_cache, cache_key, HISTORY_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached
    if not index_name:
        return _history_payload(ticker.upper(), [], unit="KRW")

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=_period_to_days(period) + 10)
    rows = await _fetch_data_go_rows(
        DATA_GO_INDEX_URL,
        _data_go_params(
            {
                "numOfRows": max(30, min(2000, _period_to_days(period) + 20)),
                "beginBasDt": start.strftime("%Y%m%d"),
                "endBasDt": end.strftime("%Y%m%d"),
                "idxNm": index_name,
            }
        ),
    )
    points = [
        point for point in (_data_go_row_to_point(row) for row in rows)
        if point is not None
    ]
    payload = _history_payload(ticker.upper(), points[-_period_to_days(period):], unit="KRW")
    if not points:
        _mark_failed_call(cache_key)
    return _cache_set(_history_cache, cache_key, payload)


async def _fetch_data_go_snapshot(ticker: str) -> dict[str, Any]:
    cache_key = f"data_go_snapshot:{ticker.upper()}"
    cached = _cache_get(_snapshot_cache, cache_key, DATA_GO_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    if _is_kr_stock(ticker):
        rows = await _fetch_data_go_rows(
            DATA_GO_STOCK_URL,
            _data_go_params({"numOfRows": 1, "likeSrtnCd": _kr_stock_code(ticker), **_recent_basdt_window()}),
        )
        history = await fetch_data_go_stock_history(ticker, "1mo")
    else:
        index_name = KR_INDEX_NAMES.get(ticker.upper())
        rows = await _fetch_data_go_rows(
            DATA_GO_INDEX_URL,
            _data_go_params({"numOfRows": 1, "idxNm": index_name, **_recent_basdt_window()}),
        ) if index_name else []
        history = await fetch_data_go_index_history(ticker, "1mo")

    row = rows[0] if rows else {}
    current_price = _safe_float(row.get("clpr"))
    change_percent = _safe_float(row.get("fltRt"))
    market_cap = _safe_float(row.get("mrktTotAmt") or row.get("lstgMrktTotAmt"))
    history_prices = [point["value"] for point in history.get("points", [])]
    if not history_prices and current_price:
        history_prices = [current_price]
    payload = {
        "currentPrice": round(current_price, 6),
        "changePercent": round(change_percent, 6),
        "history_prices": history_prices,
        "marketCap": market_cap,
    }
    return _cache_set(_snapshot_cache, cache_key, payload)


async def fetch_coingecko_history(ticker: str, period: str = "1y") -> dict[str, Any]:
    key = _coingecko_key()
    coin_id = COINGECKO_TICKER_MAP.get(ticker.upper())
    cache_key = f"coingecko:{ticker.upper()}:{period}"
    cached = _cache_get(_history_cache, cache_key, HISTORY_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached
    if not key or not coin_id:
        return _history_payload(ticker.upper(), [])

    payload = await _get_json(
        "coingecko",
        f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart",
        params={"vs_currency": "usd", "days": _period_to_days(period), "interval": "daily"},
        headers={"x-cg-demo-api-key": key},
    )
    points: list[dict[str, Any]] = []
    for raw_ts, raw_price in (payload or {}).get("prices", []):
        try:
            date = datetime.fromtimestamp(float(raw_ts) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError):
            continue
        points.append({"date": date, "value": _safe_float(raw_price)})
    history = _history_payload(ticker.upper(), points)
    if not points:
        _mark_failed_call(cache_key)
    return _cache_set(_history_cache, cache_key, history)


async def fetch_market_snapshot(ticker: str, category: str | None = None) -> dict[str, Any]:
    normalized = (ticker or "").strip().upper()
    category = (category or "").strip().upper()
    cache_key = f"snapshot:{category}:{normalized}"
    cached = _cache_get(_snapshot_cache, cache_key, SNAPSHOT_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    try:
        if category == "STOCK_US" or normalized in US_STOCK_SYMBOLS:
            payload = await _fetch_finnhub_stock_snapshot(normalized)
        elif category == "CRYPTO" or _is_crypto(normalized):
            payload = await _fetch_coingecko_snapshot(normalized)
        elif category == "FX" or normalized == "KRW=X":
            payload = await _fetch_fx_snapshot(normalized)
        elif category == "STOCK_KR" or _is_kr_stock(normalized):
            payload = await _fetch_data_go_snapshot(normalized)
        elif category == "INDEX" and normalized in KR_INDEX_NAMES:
            payload = await _fetch_data_go_snapshot(normalized)
        elif category == "INDEX":
            payload = await _fetch_stooq_snapshot(normalized)
        elif category == "COMMODITY" or _is_commodity(normalized):
            payload = await _fetch_stooq_snapshot(normalized)
        else:
            payload = dict(DEFAULT_RESPONSE)
    except Exception as exc:
        logger.warning("Market snapshot provider failed (ticker=%s, category=%s): %s", normalized, category, redact_secrets(repr(exc)))
        payload = dict(DEFAULT_RESPONSE)

    return _cache_set(_snapshot_cache, cache_key, payload)


async def fetch_market_history(ticker: str, period: str = "1y") -> dict[str, Any]:
    normalized = (ticker or "").strip().upper()
    cache_key = f"history:{normalized}:{period}"
    cached = _cache_get(_history_cache, cache_key, HISTORY_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    try:
        if normalized in US_STOCK_SYMBOLS or normalized in {"^GSPC", "^NDX"} or _is_commodity(normalized):
            payload = await fetch_stooq_history(normalized, period)
        elif _is_crypto(normalized):
            payload = await fetch_coingecko_history(normalized, period)
        elif normalized == "KRW=X":
            # stooq의 일별 USD/KRW 종가로 실제 시계열을 만든다. stooq에 데이터가 없으면
            # open.er-api 현재 환율 단일 포인트로 폴백한다.
            stooq_history = await fetch_stooq_history(normalized, period)
            points = list(stooq_history.get("points", []))
            if not points:
                snapshot = await _fetch_fx_snapshot(normalized)
                if snapshot.get("currentPrice"):
                    as_of = (
                        snapshot.get("provider_meta", {}).get("as_of")
                        or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    )
                    date = str(as_of)[:10]
                    points.append({"date": date, "value": snapshot["currentPrice"]})
            payload = _history_payload(normalized, points, unit="KRW")
        elif _is_kr_stock(normalized):
            payload = await fetch_data_go_stock_history(normalized, period)
        elif normalized in KR_INDEX_NAMES:
            payload = await fetch_data_go_index_history(normalized, period)
        else:
            payload = _history_payload(normalized, [])
    except Exception as exc:
        logger.warning("Market history provider failed (ticker=%s, period=%s): %s", normalized, period, redact_secrets(repr(exc)))
        payload = _history_payload(normalized, [])

    return _cache_set(_history_cache, cache_key, payload)


def _parse_finnhub_news(items: Any, limit: int) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return parsed
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("headline") or item.get("title") or "").strip()
        link = str(item.get("url") or "").strip()
        source = str(item.get("source") or "Finnhub").strip()
        summary = str(item.get("summary") or "").strip()
        published_at = item.get("datetime")
        if isinstance(published_at, (int, float)):
            published_at = datetime.fromtimestamp(published_at, tz=timezone.utc).isoformat()
        if not title and not link:
            continue
        parsed.append(
            {
                "title": title,
                "link": link,
                "source": source,
                "published_at": str(published_at or ""),
                "summary": summary,
                "type": "news",
            }
        )
    return parsed


async def _fetch_finnhub_company_news(symbol: str, limit: int = 5) -> list[dict[str, Any]]:
    token = _finnhub_token()
    if not token:
        return []
    today = datetime.now(timezone.utc).date()
    week_ago = today - timedelta(days=7)
    payload = await _get_json(
        "finnhub",
        f"{FINNHUB_BASE_URL}/company-news",
        params={
            "symbol": symbol,
            "from": week_ago.isoformat(),
            "to": today.isoformat(),
            "token": token,
        },
    )
    return _parse_finnhub_news(payload, limit)


async def _fetch_finnhub_category_news(category: str, limit: int = 5) -> list[dict[str, Any]]:
    token = _finnhub_token()
    if not token:
        return []
    payload = await _get_json(
        "finnhub",
        f"{FINNHUB_BASE_URL}/news",
        params={"category": category, "token": token},
    )
    return _parse_finnhub_news(payload, limit)


async def _fetch_naver_finance_news(ticker: str, limit: int = 5) -> list[dict[str, Any]]:
    code = _kr_stock_code(ticker)
    query = f"{code} {ticker}"
    text = await _get_text(
        "naver_news",
        NAVER_NEWS_URL,
        params={"where": "news", "query": query},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=8.0,
    )
    items: list[dict[str, Any]] = []
    pattern = re.compile(
        r'<a[^>]+class="[^"]*news_tit[^"]*"[^>]+href="(?P<link>[^"]+)"[^>]*title="(?P<title>[^"]*)"',
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        title = html.unescape(match.group("title")).strip()
        link = html.unescape(match.group("link")).strip()
        if not title and not link:
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "source": "Naver Finance News",
                "published_at": "",
                "summary": "",
                "type": "news",
            }
        )
        if len(items) >= limit:
            break
    return items


async def fetch_market_news_items(ticker: str, limit: int = 5) -> list[dict[str, Any]]:
    normalized = (ticker or "").strip().upper()
    cache_key = f"news:{normalized}:{limit}"
    cached = _cache_get(_snapshot_cache, cache_key, settings.MARKET_NEWS_REFRESH_MINUTES * 60)
    if cached is not None:
        return cached

    try:
        if normalized in US_STOCK_SYMBOLS:
            items = await _fetch_finnhub_company_news(normalized, limit)
        elif _is_kr_stock(normalized):
            items = await _fetch_naver_finance_news(normalized, limit)
        elif _is_crypto(normalized):
            items = await _fetch_finnhub_category_news("crypto", limit)
        elif normalized == "KRW=X":
            items = await _fetch_finnhub_category_news("forex", limit)
        else:
            items = await _fetch_finnhub_category_news("general", limit)
    except Exception as exc:
        logger.warning("Market news provider failed (ticker=%s): %s", normalized, redact_secrets(repr(exc)))
        items = []
    return _cache_set(_snapshot_cache, cache_key, items)


async def fetch_finnhub_earnings_events(symbol: str, limit: int = 8) -> list[dict[str, Any]]:
    token = _finnhub_token()
    if not token or symbol.upper() not in US_STOCK_SYMBOLS:
        return []
    today = datetime.now(timezone.utc).date()
    month_ago = today - timedelta(days=30)
    payload = await _get_json(
        "finnhub",
        f"{FINNHUB_BASE_URL}/calendar/earnings",
        params={
            "from": month_ago.isoformat(),
            "to": today.isoformat(),
            "symbol": symbol.upper(),
            "token": token,
        },
    )
    rows = (payload or {}).get("earningsCalendar", [])
    events: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return events
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        title = f"{row.get('symbol', symbol.upper())} earnings"
        value_parts = [
            f"date={row.get('date')}" if row.get("date") else "",
            f"epsActual={row.get('epsActual')}" if row.get("epsActual") not in (None, "") else "",
            f"epsEstimate={row.get('epsEstimate')}" if row.get("epsEstimate") not in (None, "") else "",
        ]
        events.append(
            {
                "title": title,
                "value": ", ".join(part for part in value_parts if part),
                "source": "Finnhub earnings calendar",
                "type": "event",
            }
        )
    return events


async def fetch_latest_provider_context(ticker: str, limit: int = 8) -> dict[str, Any]:
    normalized = (ticker or "").strip().upper()
    news_items = await fetch_market_news_items(normalized, limit=limit)
    try:
        events = await fetch_finnhub_earnings_events(normalized, limit=limit)
    except Exception as exc:
        logger.warning("Market events provider failed (ticker=%s): %s", normalized, redact_secrets(repr(exc)))
        events = []
    return {"news": news_items[:limit], "events": events[:limit]}

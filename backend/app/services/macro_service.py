from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from time import monotonic
from typing import Any

import httpx
import yfinance as yf

from ..core.config import settings

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
ECOS_BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
KR_BOND_STAT_CODE = "817Y002"
KR_BOND_TICKER_TO_ITEM_CODE = {
    "KTB_1Y": "010190000",
    "KTB_3Y": "010200000",
    "KTB_5Y": "010200001",
    "KTB_10Y": "010210000",
    "KTB_20Y": "010220000",
    "KTB_30Y": "010230000",
}
LEGACY_KR_BOND_CODES = {"0101500", "0102000"}
FAILED_CALL_TTL_SECONDS = 300

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY") or settings.ALPHA_VANTAGE_API_KEY
ECOS_API_KEY = os.getenv("ECOS_API_KEY") or settings.ECOS_API_KEY

DEFAULT_RESPONSE = {
    "currentPrice": 0.0,
    "changePercent": 0.0,
    "history_prices": [],
    "marketCap": 0.0,
}
DEFAULT_HISTORY_RESPONSE: list[dict[str, Any]] = []

_failed_call_cache: dict[str, float] = {}


def _normalize_history(history_prices: list[float]) -> dict[str, Any]:
    if not history_prices:
        return DEFAULT_RESPONSE

    current_price = float(history_prices[-1])
    prev_price = float(history_prices[-2]) if len(history_prices) >= 2 else current_price
    change_percent = 0.0 if prev_price == 0 else ((current_price - prev_price) / prev_price) * 100

    return {
        "currentPrice": round(current_price, 6),
        "changePercent": round(change_percent, 6),
        "history_prices": [round(float(v), 6) for v in history_prices],
        "marketCap": 0.0,
    }


def _format_ecos_date(time_value: str) -> str:
    """
    ECOS TIME examples:
    - daily: YYYYMMDD
    - monthly: YYYYMM
    """
    raw = str(time_value or "").strip()
    if len(raw) == 8:
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    if len(raw) == 6:
        return f"{raw[0:4]}-{raw[4:6]}-01"
    return raw


def _parse_ecos_history_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for row in rows:
        value = row.get("DATA_VALUE")
        time_value = row.get("TIME")
        if value in (None, "") or time_value in (None, ""):
            continue
        try:
            close_value = float(value)
        except (TypeError, ValueError):
            continue
        parsed.append(
            {
                "date": _format_ecos_date(str(time_value)),
                "close": close_value,
                "value": close_value,
            }
        )

    # Chronological order: oldest -> latest
    parsed.sort(key=lambda x: x["date"])
    return parsed[-30:]


def _normalize_kr_bond_item_code(asset_ticker: str) -> str:
    normalized = (asset_ticker or "").strip().upper()
    if normalized in KR_BOND_TICKER_TO_ITEM_CODE:
        return KR_BOND_TICKER_TO_ITEM_CODE[normalized]
    if normalized in LEGACY_KR_BOND_CODES:
        # backward compatibility: legacy caller passes ECOS item code directly
        return normalized
    raise ValueError(f"Unsupported KR bond ticker/item code: {asset_ticker}")


def _build_ecos_date_range(lookback_days: int = 90, end_date: datetime | None = None) -> tuple[str, str]:
    safe_lookback = max(7, int(lookback_days))
    now = datetime.now()
    end = end_date or now
    if end > now:
        end = now
    start = end - timedelta(days=safe_lookback)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def _should_skip_failed_call(key: str) -> bool:
    last_failed_at = _failed_call_cache.get(key)
    if last_failed_at is None:
        return False
    if monotonic() - last_failed_at < FAILED_CALL_TTL_SECONDS:
        return True
    _failed_call_cache.pop(key, None)
    return False


def _mark_failed_call(key: str) -> None:
    _failed_call_cache[key] = monotonic()


async def fetch_commodity_data(ticker: str) -> dict[str, Any]:
    normalized_ticker = (ticker or "").strip().upper()
    if normalized_ticker in {"XAU", "GC=F"}:
        yf_ticker = "GC=F"
    elif normalized_ticker in {"XAG", "SI=F"}:
        yf_ticker = "SI=F"
    else:
        yf_ticker = normalized_ticker

    try:
        ticker_obj = yf.Ticker(yf_ticker)
        hist = await asyncio.to_thread(ticker_obj.history, period="1mo")
        if hist.empty:
            logger.warning("Empty commodity history from yfinance: %s", yf_ticker)
            return DEFAULT_RESPONSE
        history_prices = [float(v) for v in hist["Close"].tolist()[-30:]]
        return _normalize_history(history_prices)
    except Exception as exc:
        logger.error("Commodity fetch error (%s): %s", yf_ticker, exc)
        return DEFAULT_RESPONSE


async def fetch_us_bond_data(series_id: str) -> dict[str, Any]:
    api_key = settings.FRED_API_KEY
    if not api_key:
        raise ValueError("FRED_API_KEY is not set")

    normalized_series_id = (series_id or "").strip().upper()
    if "2MO" in normalized_series_id:
        logger.info("FRED series remap: %s -> DGS3MO", normalized_series_id)
        normalized_series_id = "DGS3MO"

    params = {
        "series_id": normalized_series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 30,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(FRED_BASE_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    observations = payload.get("observations", [])
    history_desc: list[float] = []
    last_valid: float | None = None
    for item in observations:
        raw_val = item.get("value")
        if raw_val in (None, "."):
            if last_valid is not None:
                history_desc.append(last_valid)
            continue
        value = float(raw_val)
        last_valid = value
        history_desc.append(value)

    history_prices = list(reversed(history_desc))
    if not history_prices:
        logger.warning("Empty US bond history from FRED: %s", normalized_series_id)
    return _normalize_history(history_prices)


async def fetch_kr_bond_data(
    asset_ticker: str,
    *,
    lookback_days: int = 90,
    end_date: datetime | None = None,
) -> dict[str, Any]:
    try:
        normalized_item_code = _normalize_kr_bond_item_code(asset_ticker)
    except ValueError as exc:
            logger.error("Invalid KR bond ticker mapping (assetTicker=%s): %s", asset_ticker, exc)
            return DEFAULT_RESPONSE

    start_date, end_date_str = _build_ecos_date_range(lookback_days=lookback_days, end_date=end_date)
    request_key = f"ecos:{KR_BOND_STAT_CODE}:{normalized_item_code}:{start_date}:{end_date_str}"

    if _should_skip_failed_call(request_key):
        logger.warning("Skipping repeated failed ECOS call: %s", request_key)
        return DEFAULT_RESPONSE

    url = (
        f"{ECOS_BASE_URL}/{ECOS_API_KEY}/json/kr/1/100/{KR_BOND_STAT_CODE}/"
        f"D/{start_date}/{end_date_str}/{normalized_item_code}"
    )

    try:
        points = await fetch_kr_bond_history(asset_ticker, lookback_days=lookback_days, end_date=end_date)
        if not points:
            _mark_failed_call(request_key)
            return DEFAULT_RESPONSE
        history_prices = [float(p["close"]) for p in points]
        return _normalize_history(history_prices)
    except Exception as exc:
        logger.error(
            "KR Bond fetch error (item=%s, start=%s, end=%s): %s",
            normalized_item_code,
            start_date,
            end_date_str,
            exc,
        )
        _mark_failed_call(request_key)
        return DEFAULT_RESPONSE


async def fetch_kr_bond_history(
    asset_ticker: str,
    *,
    lookback_days: int = 90,
    end_date: datetime | None = None,
) -> list[dict[str, Any]]:
    try:
        normalized_item_code = _normalize_kr_bond_item_code(asset_ticker)
    except ValueError as exc:
        logger.error("Invalid KR bond ticker mapping (assetTicker=%s): %s", asset_ticker, exc)
        return DEFAULT_HISTORY_RESPONSE

    start_date, end_date_str = _build_ecos_date_range(lookback_days=lookback_days, end_date=end_date)
    request_key = f"ecos_history:{KR_BOND_STAT_CODE}:{normalized_item_code}:{start_date}:{end_date_str}"
    if _should_skip_failed_call(request_key):
        logger.warning("Skipping repeated failed ECOS history call: %s", request_key)
        return DEFAULT_HISTORY_RESPONSE

    url = (
        f"{ECOS_BASE_URL}/{ECOS_API_KEY}/json/kr/1/100/{KR_BOND_STAT_CODE}/"
        f"D/{start_date}/{end_date_str}/{normalized_item_code}"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        result = payload.get("RESULT")
        if isinstance(result, dict) and result.get("CODE"):
            logger.error(
                "ECOS API Error (code=%s, assetTicker=%s, item=%s, start=%s, end=%s): %s",
                result.get("CODE"),
                asset_ticker,
                normalized_item_code,
                start_date,
                end_date_str,
                result.get("MESSAGE"),
            )
            _mark_failed_call(request_key)
            return DEFAULT_HISTORY_RESPONSE

        rows = payload.get("StatisticSearch", {}).get("row", [])
        if not rows:
            logger.warning(
                "ECOS returned no data for ticker=%s, item_code=%s, range=%s~%s",
                asset_ticker,
                normalized_item_code,
                start_date,
                end_date_str,
            )
            _mark_failed_call(request_key)
            return DEFAULT_HISTORY_RESPONSE

        points = _parse_ecos_history_rows(rows)
        if not points:
            logger.warning(
                "ECOS rows had no usable TIME/DATA_VALUE (ticker=%s, item_code=%s, range=%s~%s)",
                asset_ticker,
                normalized_item_code,
                start_date,
                end_date_str,
            )
            _mark_failed_call(request_key)
            return DEFAULT_HISTORY_RESPONSE
        return points
    except Exception as exc:
        logger.error(
            "KR Bond history fetch error (item=%s, start=%s, end=%s): %s",
            normalized_item_code,
            start_date,
            end_date_str,
            exc,
        )
        _mark_failed_call(request_key)
        return DEFAULT_HISTORY_RESPONSE

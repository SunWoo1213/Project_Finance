import pytest

from app.core.cache import market_cache
from app.services import market_service, price_providers


def setup_function():
    price_providers._failed_call_cache.clear()
    price_providers._snapshot_cache.clear()
    price_providers._profile_cache.clear()
    price_providers._history_cache.clear()
    market_cache.setdefault("latest_context", {}).clear()


def test_parse_stooq_csv_preserves_provider_dates():
    csv_text = "Date,Open,High,Low,Close,Volume\n2026-05-31,1,2,1,10,100\n2026-06-02,1,2,1,12,100\n"

    points = price_providers._parse_stooq_csv(csv_text)

    assert points == [
        {"date": "2026-05-31", "value": 10.0},
        {"date": "2026-06-02", "value": 12.0},
    ]


def test_parse_stooq_csv_degrades_when_key_required():
    assert price_providers._parse_stooq_csv("Get your apikey: open stooq") == []


@pytest.mark.asyncio
async def test_coingecko_history_requires_demo_key(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "COINGECKO_DEMO_API_KEY", None)

    payload = await price_providers.fetch_coingecko_history("BTC-USD", "1mo")

    assert payload["points"] == []
    assert payload["legacy"] == []


@pytest.mark.asyncio
async def test_market_history_uses_ticker_period_cache(monkeypatch):
    calls = {"count": 0}

    async def fake_stooq_history(ticker, period):
        calls["count"] += 1
        return {
            "ticker": ticker,
            "series_type": "price",
            "unit": "USD",
            "points": [{"date": "2026-06-02", "value": 100.0}],
            "legacy": [{"date": "2026-06-02", "close": 100.0, "value": 100.0}],
        }

    monkeypatch.setattr(price_providers, "fetch_stooq_history", fake_stooq_history)

    first = await price_providers.fetch_market_history("AAPL", "1mo")
    second = await price_providers.fetch_market_history("AAPL", "1mo")

    assert first == second
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_latest_context_force_refresh_respects_cooldown(monkeypatch):
    calls = {"count": 0}

    async def fake_context(ticker):
        calls["count"] += 1
        return {"news": [{"title": "A", "link": "", "source": "test"}], "events": []}

    monkeypatch.setattr(market_service, "fetch_latest_provider_context", fake_context)

    first = await market_service.fetch_latest_asset_context("AAPL", force_refresh=True)
    second = await market_service.fetch_latest_asset_context("AAPL", force_refresh=True)

    assert first == second
    assert calls["count"] == 1

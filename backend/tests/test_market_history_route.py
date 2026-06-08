import pytest
from fastapi import HTTPException

from app import main


@pytest.mark.asyncio
async def test_get_market_history_returns_404_on_empty_macro_data(monkeypatch):
    monkeypatch.setattr(main.settings, "MARKET_LIVE_TICKERS", "KTB_1Y")

    async def fake_fetch_kr_bond_history(*args, **kwargs):
        return []

    monkeypatch.setattr(main, "fetch_kr_bond_history", fake_fetch_kr_bond_history)

    with pytest.raises(HTTPException) as exc_info:
        await main.get_market_history("KTB_1Y", "1y")

    assert exc_info.value.status_code == 404
    assert "No KR bond history found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_market_history_calls_kr_bond_service_with_asset_ticker(monkeypatch):
    monkeypatch.setattr(main.settings, "MARKET_LIVE_TICKERS", "KTB_10Y")
    captured = {"ticker": None}

    async def fake_fetch_kr_bond_history(ticker, **kwargs):
        captured["ticker"] = ticker
        return [{"date": "2026-05-30", "value": 2.0}, {"date": "2026-05-31", "value": 2.1}]

    monkeypatch.setattr(main, "fetch_kr_bond_history", fake_fetch_kr_bond_history)
    result = await main.get_market_history("KTB_10Y", "1y")

    assert captured["ticker"] == "KTB_10Y"
    assert result["series_type"] == "yield"
    assert result["unit"] == "%"
    assert len(result["points"]) == 2


@pytest.mark.asyncio
async def test_get_market_history_preserves_us_bond_provider_dates(monkeypatch):
    captured = {"ticker": None, "limit": None}

    async def fake_fetch_us_bond_history(ticker, limit=30):
        captured["ticker"] = ticker
        captured["limit"] = limit
        return [{"date": "2026-06-01", "value": 4.4}, {"date": "2026-06-03", "value": 4.5}]

    monkeypatch.setattr(main, "fetch_us_bond_history", fake_fetch_us_bond_history)

    result = await main.get_market_history("DGS10", "1mo")

    assert captured == {"ticker": "DGS10", "limit": 30}
    assert result["series_type"] == "yield"
    assert result["unit"] == "%"
    assert result["points"] == [{"date": "2026-06-01", "value": 4.4}, {"date": "2026-06-03", "value": 4.5}]
    assert result["provider_meta"]["provider"] == "fred"


@pytest.mark.asyncio
async def test_get_market_history_passes_provider_metadata(monkeypatch):
    monkeypatch.setattr(main.settings, "MARKET_LIVE_TICKERS", "KRW=X")

    async def fake_fetch_market_history(ticker, period):
        return {
            "ticker": ticker,
            "series_type": "price",
            "unit": "KRW",
            "points": [{"date": "2026-06-03", "value": 1386.0}],
            "legacy": [{"date": "2026-06-03", "close": 1386.0, "value": 1386.0}],
            "provider_meta": {"provider": "open.er-api.com", "freshness": "daily_reference"},
        }

    monkeypatch.setattr(main, "fetch_market_history", fake_fetch_market_history)

    result = await main.get_market_history("KRW=X", "1d")

    assert result["provider_meta"] == {"provider": "open.er-api.com", "freshness": "daily_reference"}


@pytest.mark.asyncio
async def test_get_market_history_mocks_non_live_tickers(monkeypatch):
    monkeypatch.setattr(main.settings, "MARKET_LIVE_TICKERS", "DGS10,XAU,BTC-USD,NVDA,005930.KS")

    async def fail_fetch_kr_bond_history(*args, **kwargs):
        raise AssertionError("non-live history should not call a provider")

    monkeypatch.setattr(main, "fetch_kr_bond_history", fail_fetch_kr_bond_history)

    result = await main.get_market_history("KTB_10Y", "1d")

    assert result["ticker"] == "KTB_10Y"
    assert result["series_type"] == "yield"
    assert result["unit"] == "%"
    assert len(result["points"]) == 7
    assert result["provider_meta"]["provider"] == "demo_mock"

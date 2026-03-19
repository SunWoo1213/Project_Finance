import pytest
from fastapi import HTTPException

from app import main


@pytest.mark.asyncio
async def test_get_market_history_returns_404_on_empty_macro_data(monkeypatch):
    async def fake_fetch_kr_bond_data(*args, **kwargs):
        return {"currentPrice": 0.0, "changePercent": 0.0, "history_prices": [], "marketCap": 0.0}

    monkeypatch.setattr(main, "fetch_kr_bond_data", fake_fetch_kr_bond_data)

    with pytest.raises(HTTPException) as exc_info:
        await main.get_market_history("KTB_1Y", "1y")

    assert exc_info.value.status_code == 404
    assert "No KR bond history found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_market_history_calls_kr_bond_service_with_asset_ticker(monkeypatch):
    captured = {"ticker": None}

    async def fake_fetch_kr_bond_data(ticker, **kwargs):
        captured["ticker"] = ticker
        return {"currentPrice": 2.1, "changePercent": 0.1, "history_prices": [2.0, 2.1], "marketCap": 0.0}

    monkeypatch.setattr(main, "fetch_kr_bond_data", fake_fetch_kr_bond_data)
    result = await main.get_market_history("KTB_10Y", "1y")

    assert captured["ticker"] == "KTB_10Y"
    assert result["series_type"] == "yield"
    assert result["unit"] == "%"
    assert len(result["points"]) == 2

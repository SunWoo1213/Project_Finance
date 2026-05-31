import pytest
from fastapi import HTTPException

from app import main


@pytest.mark.asyncio
async def test_get_market_history_returns_404_on_empty_macro_data(monkeypatch):
    async def fake_fetch_kr_bond_history(*args, **kwargs):
        return []

    monkeypatch.setattr(main, "fetch_kr_bond_history", fake_fetch_kr_bond_history)

    with pytest.raises(HTTPException) as exc_info:
        await main.get_market_history("KTB_1Y", "1y")

    assert exc_info.value.status_code == 404
    assert "No KR bond history found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_market_history_calls_kr_bond_service_with_asset_ticker(monkeypatch):
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

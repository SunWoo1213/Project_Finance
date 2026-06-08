from datetime import datetime, timedelta

import pytest

from app.services import macro_service


def test_normalize_kr_bond_item_code_keeps_valid_code():
    assert macro_service._normalize_kr_bond_item_code("0101500") == "0101500"
    assert macro_service._normalize_kr_bond_item_code("0102000") == "0102000"


def test_normalize_kr_bond_ticker_to_ecos_item_code():
    assert macro_service._normalize_kr_bond_item_code("KTB_1Y") == "010190000"
    assert macro_service._normalize_kr_bond_item_code("KTB_10Y") == "010210000"


def test_build_ecos_date_range_clamps_future_end_date():
    future = datetime.now() + timedelta(days=30)
    start_date, end_date = macro_service._build_ecos_date_range(lookback_days=90, end_date=future)
    assert int(end_date) <= int(datetime.now().strftime("%Y%m%d"))
    assert int(start_date) < int(end_date)


@pytest.mark.asyncio
async def test_fetch_kr_bond_data_with_invalid_ticker_returns_default():
    result = await macro_service.fetch_kr_bond_data("NOT_A_KTB", lookback_days=90)
    assert result["history_prices"] == []
    assert result["currentPrice"] == 0.0


@pytest.mark.asyncio
async def test_fetch_kr_bond_data_uses_exact_item_code(monkeypatch):
    captured = {"url": None}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "StatisticSearch": {
                    "row": [
                        {"TIME": "20260529", "DATA_VALUE": "2.50"},
                        {"TIME": "20260530", "DATA_VALUE": "2.60"},
                        {"TIME": "20260531", "DATA_VALUE": "2.70"},
                    ]
                }
            }

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            captured["url"] = url
            return DummyResponse()

    monkeypatch.setattr(macro_service.httpx, "AsyncClient", DummyClient)
    result = await macro_service.fetch_kr_bond_data("KTB_1Y", lookback_days=90)

    assert "/010190000" in captured["url"]
    assert result["history_prices"]
    assert isinstance(result["currentPrice"], float)


@pytest.mark.asyncio
async def test_fetch_kr_bond_data_skips_repeated_failed_calls(monkeypatch):
    call_counter = {"count": 0}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            call_counter["count"] += 1
            return DummyResponse()

    monkeypatch.setattr(macro_service.httpx, "AsyncClient", DummyClient)
    macro_service._failed_call_cache.clear()

    first = await macro_service.fetch_kr_bond_data("KTB_1Y", lookback_days=90)
    second = await macro_service.fetch_kr_bond_data("KTB_1Y", lookback_days=90)

    assert first["history_prices"] == []
    assert second["history_prices"] == []
    assert call_counter["count"] == 1


@pytest.mark.asyncio
async def test_fetch_us_bond_history_preserves_fred_observation_dates(monkeypatch):
    monkeypatch.setattr(macro_service.settings, "FRED_API_KEY", "test-key")
    captured = {"params": None}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "observations": [
                    {"date": "2026-06-03", "value": "4.50"},
                    {"date": "2026-06-02", "value": "."},
                    {"date": "2026-06-01", "value": "4.40"},
                ]
            }

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            captured["params"] = params
            return DummyResponse()

    monkeypatch.setattr(macro_service.httpx, "AsyncClient", DummyClient)

    points = await macro_service.fetch_us_bond_history("DGS10", limit=3)

    assert captured["params"]["series_id"] == "DGS10"
    assert captured["params"]["limit"] == 3
    assert points == [
        {"date": "2026-06-01", "value": 4.4},
        {"date": "2026-06-02", "value": 4.5},
        {"date": "2026-06-03", "value": 4.5},
    ]

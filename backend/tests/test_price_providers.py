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


def test_kr_index_names_use_korean_idxnm():
    # data.go.kr getStockMarketIndex matches idxNm by Korean name; English forms
    # return empty results. Guard against a regression to "KOSPI"/"KOSDAQ".
    assert price_providers.KR_INDEX_NAMES["^KS11"] == "코스피"
    assert price_providers.KR_INDEX_NAMES["^KQ11"] == "코스닥"


def test_recent_basdt_window_is_ordered_yyyymmdd():
    window = price_providers._recent_basdt_window(days=20)
    assert set(window) == {"beginBasDt", "endBasDt"}
    assert len(window["beginBasDt"]) == 8 and window["beginBasDt"].isdigit()
    assert len(window["endBasDt"]) == 8 and window["endBasDt"].isdigit()
    assert window["beginBasDt"] < window["endBasDt"]


def test_data_go_semaphore_uses_configured_concurrency(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "DATA_GO_KR_MAX_CONCURRENCY", 2)
    price_providers._provider_semaphores.clear()

    data_go = price_providers._provider_semaphore("data_go_kr")
    other = price_providers._provider_semaphore("finnhub")

    # asyncio.Semaphore exposes its current count via the private _value attr.
    assert data_go._value == 2
    assert other._value == 1
    price_providers._provider_semaphores.clear()


@pytest.mark.asyncio
async def test_data_go_rows_use_configured_timeout(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "DATA_GO_KR_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "DATA_GO_KR_FETCH_TIMEOUT_SECONDS", 25)
    captured = {}

    async def fake_get_json(provider, url, *, params=None, headers=None, timeout=10.0):
        captured["provider"] = provider
        captured["timeout"] = timeout
        return {}

    monkeypatch.setattr(price_providers, "_get_json", fake_get_json)

    await price_providers._fetch_data_go_rows("http://example", {"numOfRows": 1})

    assert captured["provider"] == "data_go_kr"
    assert captured["timeout"] == 25.0


@pytest.mark.asyncio
async def test_kr_index_snapshot_query_uses_korean_name_and_date_window(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "DATA_GO_KR_API_KEY", "test-key")
    captured = {}

    async def fake_rows(url, params):
        captured["url"] = url
        captured["params"] = params
        return []

    async def fake_index_history(ticker, period):
        return price_providers._history_payload(ticker, [], unit="KRW")

    monkeypatch.setattr(price_providers, "_fetch_data_go_rows", fake_rows)
    monkeypatch.setattr(price_providers, "fetch_data_go_index_history", fake_index_history)

    await price_providers._fetch_data_go_snapshot("^KS11")

    assert captured["url"] == price_providers.DATA_GO_INDEX_URL
    assert captured["params"]["idxNm"] == "코스피"
    assert "beginBasDt" in captured["params"] and "endBasDt" in captured["params"]


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
async def test_fx_snapshot_change_percent_from_stooq_close(monkeypatch):
    async def fake_get_json(provider, url, **kwargs):
        return {"rates": {"KRW": 1386.0}, "provider": "open.er-api.com"}

    async def fake_stooq_history(ticker, period):
        assert ticker == "KRW=X"
        return price_providers._history_payload(
            "KRW=X",
            [
                {"date": "2026-06-02", "value": 1370.0},
                {"date": "2026-06-03", "value": 1380.0},
            ],
            unit="KRW",
        )

    monkeypatch.setattr(price_providers, "_get_json", fake_get_json)
    monkeypatch.setattr(price_providers, "fetch_stooq_history", fake_stooq_history)

    snapshot = await price_providers._fetch_fx_snapshot("KRW=X")

    # 현재 환율(1386) vs stooq 최신 종가(1380) → 약 +0.4348%, 더 이상 0이 아니다.
    assert snapshot["currentPrice"] == 1386.0
    assert snapshot["changePercent"] != 0.0
    assert snapshot["changePercent"] == round(((1386.0 - 1380.0) / 1380.0) * 100, 6)
    assert snapshot["provider_meta"]["change_source"] == "stooq"


@pytest.mark.asyncio
async def test_fx_snapshot_falls_back_when_stooq_empty(monkeypatch):
    async def fake_get_json(provider, url, **kwargs):
        return {"rates": {"KRW": 1386.0}, "provider": "open.er-api.com"}

    async def fake_stooq_history(ticker, period):
        return price_providers._history_payload("KRW=X", [], unit="KRW")

    monkeypatch.setattr(price_providers, "_get_json", fake_get_json)
    monkeypatch.setattr(price_providers, "fetch_stooq_history", fake_stooq_history)

    snapshot = await price_providers._fetch_fx_snapshot("KRW=X")

    assert snapshot["currentPrice"] == 1386.0
    assert snapshot["changePercent"] == 0.0
    assert snapshot["provider_meta"]["change_source"] == "none"


@pytest.mark.asyncio
async def test_finnhub_stock_snapshot_keeps_quote_when_optional_sources_fail(monkeypatch):
    async def fake_get_json(provider, url, **kwargs):
        assert provider == "finnhub"
        return {"c": 125.5, "pc": 120.0, "dp": 4.58}

    async def failing_market_cap(symbol):
        raise TimeoutError("profile timeout")

    async def failing_stooq_history(ticker, period):
        raise TimeoutError("stooq timeout")

    monkeypatch.setattr(price_providers.settings, "FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(price_providers, "_get_json", fake_get_json)
    monkeypatch.setattr(price_providers, "_fetch_finnhub_profile_market_cap", failing_market_cap)
    monkeypatch.setattr(price_providers, "fetch_stooq_history", failing_stooq_history)

    snapshot = await price_providers._fetch_finnhub_stock_snapshot("NVDA")

    assert snapshot["currentPrice"] == 125.5
    assert snapshot["changePercent"] == 4.58
    assert snapshot["marketCap"] == 0.0
    assert snapshot["history_prices"] == [125.5]


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

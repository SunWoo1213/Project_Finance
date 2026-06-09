import asyncio

import pytest

from app.core.config import Settings
from app.services import market_service


def test_fetch_timeout_settings_enforce_minimum():
    settings = Settings(
        MARKET_PRICE_FETCH_TIMEOUT_SECONDS=1,
        MARKET_NEWS_FETCH_TIMEOUT_SECONDS=0,
    )
    assert settings.MARKET_PRICE_FETCH_TIMEOUT_SECONDS == 5
    assert settings.MARKET_NEWS_FETCH_TIMEOUT_SECONDS == 5


def test_fetch_timeout_settings_accept_configured_values():
    settings = Settings(
        MARKET_PRICE_FETCH_TIMEOUT_SECONDS=45,
        MARKET_NEWS_FETCH_TIMEOUT_SECONDS=25,
    )
    assert settings.MARKET_PRICE_FETCH_TIMEOUT_SECONDS == 45
    assert settings.MARKET_NEWS_FETCH_TIMEOUT_SECONDS == 25


def test_price_fetch_timeout_default_covers_two_data_go_calls():
    # KR stock snapshot makes two data.go.kr calls; the per-asset price timeout
    # default must stay above 2 * DATA_GO_KR_FETCH_TIMEOUT_SECONDS or an
    # uncontended KR asset can never finish. Checked on code defaults (not env).
    price_default = Settings.model_fields["MARKET_PRICE_FETCH_TIMEOUT_SECONDS"].default
    data_go_default = Settings.model_fields["DATA_GO_KR_FETCH_TIMEOUT_SECONDS"].default
    assert price_default >= 2 * data_go_default


def test_data_go_settings_enforce_minimums():
    settings = Settings(
        DATA_GO_KR_FETCH_TIMEOUT_SECONDS=1,
        DATA_GO_KR_MAX_CONCURRENCY=0,
    )
    assert settings.DATA_GO_KR_FETCH_TIMEOUT_SECONDS == 5
    assert settings.DATA_GO_KR_MAX_CONCURRENCY == 1


def test_data_go_settings_accept_configured_values():
    settings = Settings(
        DATA_GO_KR_FETCH_TIMEOUT_SECONDS=30,
        DATA_GO_KR_MAX_CONCURRENCY=3,
    )
    assert settings.DATA_GO_KR_FETCH_TIMEOUT_SECONDS == 30
    assert settings.DATA_GO_KR_MAX_CONCURRENCY == 3


def test_fmp_settings_enforce_minimums():
    settings = Settings(
        FMP_FETCH_TIMEOUT_SECONDS=1,
        FMP_DAILY_CALL_BUDGET=-1,
    )
    assert settings.FMP_FETCH_TIMEOUT_SECONDS == 5
    assert settings.FMP_DAILY_CALL_BUDGET == 0


def test_fmp_settings_accept_configured_values():
    settings = Settings(
        FMP_FETCH_TIMEOUT_SECONDS=15,
        FMP_DAILY_CALL_BUDGET=120,
        ENABLE_STOOQ_FALLBACK=True,
    )
    assert settings.FMP_FETCH_TIMEOUT_SECONDS == 15
    assert settings.FMP_DAILY_CALL_BUDGET == 120
    assert settings.ENABLE_STOOQ_FALLBACK is True


def test_stooq_fallback_is_disabled_by_default():
    assert Settings.model_fields["ENABLE_STOOQ_FALLBACK"].default is False


@pytest.mark.asyncio
async def test_collect_prices_group_times_out_slow_asset_without_blocking_others(monkeypatch):
    # A slow asset must not block fast assets in the same group. On timeout the
    # label is kept (carry-forward/placeholder) so its card does not vanish from
    # the UI, while the fast asset still resolves with live data.
    monkeypatch.setattr(market_service.settings, "MARKET_PRICE_FETCH_TIMEOUT_SECONDS", 1)
    market_service.market_cache.setdefault("prices", {}).pop("test", None)
    # Force the live-fetch path so the timeout branch is exercised regardless of
    # the environment's MARKET_LIVE_TICKERS allowlist.
    monkeypatch.setattr(market_service, "is_live_market_ticker", lambda ticker: True)

    async def fake_fetch(ticker, category):
        if ticker == "SLOW":
            await asyncio.sleep(5)  # exceeds the 1s configured timeout
        return {
            "currentPrice": 10.0,
            "changePercent": 1.0,
            "history_prices": [10.0],
            "marketCap": 0.0,
        }

    monkeypatch.setattr(market_service, "fetch_asset_data", fake_fetch)

    assets = {
        "Fast": {"ticker": "FAST", "category": "STOCK_US"},
        "Slow": {"ticker": "SLOW", "category": "STOCK_US"},
    }

    group_name, results = await market_service._collect_prices_group("test", assets)

    assert group_name == "test"
    assert "Fast" in results
    assert results["Fast"]["currentPrice"] == 10.0
    # No prior cache for SLOW -> kept as a zero placeholder, never dropped.
    assert "Slow" in results
    assert results["Slow"]["currentPrice"] == 0.0


@pytest.mark.asyncio
async def test_collect_prices_group_carries_forward_last_value_on_failure(monkeypatch):
    # 실패(예외) 시 직전 유효 캐시값을 이어 써서 라벨(=카드)이 사라지지 않는다.
    prior = {
        "symbol": "^NDX",
        "price": 100.0,
        "change_pct": 1.0,
        "history_prices": [100.0],
        "marketCap": 0.0,
        "currentPrice": 100.0,
        "changePercent": 1.0,
    }
    market_service.market_cache.setdefault("prices", {})["test"] = {"Nasdaq 100": prior}

    async def failing_fetch(ticker, category):
        raise RuntimeError("provider down")

    monkeypatch.setattr(market_service, "is_live_market_ticker", lambda ticker: True)
    monkeypatch.setattr(market_service, "fetch_asset_data", failing_fetch)

    assets = {"Nasdaq 100": {"ticker": "^NDX", "category": "INDEX"}}

    _, results = await market_service._collect_prices_group("test", assets)

    assert "Nasdaq 100" in results
    assert results["Nasdaq 100"]["price"] == 100.0
    assert results["Nasdaq 100"]["change_pct"] == 1.0

    market_service.market_cache.get("prices", {}).pop("test", None)


@pytest.mark.asyncio
async def test_collect_news_group_times_out_slow_symbol(monkeypatch):
    monkeypatch.setattr(market_service.settings, "MARKET_NEWS_FETCH_TIMEOUT_SECONDS", 1)
    # Force the live-fetch path so the timeout branch is exercised regardless of
    # the environment's MARKET_LIVE_TICKERS allowlist.
    monkeypatch.setattr(market_service, "is_live_market_ticker", lambda ticker: True)

    async def fake_news(symbol):
        if symbol == "SLOW":
            await asyncio.sleep(5)
        return [{"title": "ok", "link": "", "source": "test"}]

    monkeypatch.setattr(market_service, "fetch_market_news_items", fake_news)

    tickers = {"Fast": "FAST", "Slow": "SLOW"}

    group_name, results = await market_service._collect_news_group("test", tickers)

    assert group_name == "test"
    assert "Fast" in results
    assert "Slow" not in results

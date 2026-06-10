import pytest

from app.core.cache import market_cache
from app.core.config import Settings
from app.services import demo_market_data, market_service, price_providers


def setup_function():
    price_providers._failed_call_cache.clear()
    price_providers._snapshot_cache.clear()
    price_providers._profile_cache.clear()
    price_providers._history_cache.clear()
    price_providers._fmp_daily_call_date = None
    price_providers._fmp_daily_call_count = 0
    market_cache.setdefault("latest_context", {}).clear()


def test_parse_stooq_csv_preserves_provider_dates():
    csv_text = "Date,Open,High,Low,Close,Volume\n2026-05-31,1,2,1,10,100\n2026-06-02,1,2,1,12,100\n"

    points = price_providers._parse_stooq_csv(csv_text)

    assert points == [
        {"date": "2026-05-31", "value": 10.0},
        {"date": "2026-06-02", "value": 12.0},
    ]


def test_demo_default_live_tickers_include_dashboard_only_not_all(monkeypatch):
    configured_default = Settings.model_fields["MARKET_LIVE_TICKERS"].default

    assert configured_default == demo_market_data.DEFAULT_LIVE_TICKERS

    monkeypatch.setattr(demo_market_data.settings, "MARKET_LIVE_TICKERS", configured_default)

    for ticker in ("^GSPC", "^NDX", "KRW=X", "^KS11"):
        assert demo_market_data.is_live_market_ticker(ticker)

    assert demo_market_data.is_live_market_ticker("NVDA")
    assert not demo_market_data.is_live_market_ticker("AAPL")
    assert not demo_market_data.is_live_market_ticker("^KQ11")


def test_parse_stooq_csv_degrades_when_key_required():
    assert price_providers._parse_stooq_csv("Get your apikey: open stooq") == []


def test_parse_stooq_challenge_detects_pow_html():
    html = (
        '<script>(async()=>{const c="SEED123",d=4,t="0".repeat(d);'
        'await fetch("/__verify",{method:"POST"})})()</script>'
    )

    assert price_providers._parse_stooq_challenge(html) == ("SEED123", 4)


def test_parse_stooq_challenge_returns_none_for_csv():
    csv_text = "Date,Open,High,Low,Close,Volume\n2026-06-01,1,2,1,19000,100\n"

    assert price_providers._parse_stooq_challenge(csv_text) is None


def test_solve_stooq_challenge_finds_valid_nonce():
    import hashlib

    nonce = price_providers._solve_stooq_challenge("seed", 2)

    assert hashlib.sha256(f"seed{nonce}".encode()).hexdigest().startswith("00")


@pytest.mark.asyncio
async def test_get_stooq_text_solves_pow_then_returns_csv(monkeypatch):
    # 첫 GET은 PoW 챌린지 HTML, /__verify POST 후 두 번째 GET에서 CSV가 내려오는
    # 실제 stooq 흐름을 가짜 httpx 클라이언트로 재현한다.
    price_providers._failed_call_cache.clear()
    price_providers._stooq_verify_cookies.clear()

    challenge_html = (
        '<script>(async()=>{const c="seed",d=2,t="0".repeat(d);'
        'await fetch("/__verify",{method:"POST"})})()</script>'
    )
    csv_text = "Date,Open,High,Low,Close,Volume\n2026-06-01,1,2,1,19000,100\n"
    calls = {"get": 0, "post": 0}

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.cookies = {"verify": "ok"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            calls["get"] += 1
            if calls["get"] == 1:
                return FakeResponse(challenge_html)
            return FakeResponse(csv_text)

        async def post(self, url, data=None):
            calls["post"] += 1
            assert data["c"] == "seed"
            assert isinstance(data["n"], int)
            return FakeResponse("ok")

    monkeypatch.setattr(price_providers.httpx, "AsyncClient", FakeClient)

    text = await price_providers._get_stooq_text({"s": "^ndx", "i": "d", "apikey": "k"}, timeout=5)

    assert text == csv_text
    assert calls == {"get": 2, "post": 1}
    assert price_providers._stooq_verify_cookies == {"verify": "ok"}


def test_parse_fmp_history_preserves_provider_dates():
    payload = {
        "historical": [
            {"date": "2026-06-02", "close": 12.0},
            {"date": "2026-05-31", "close": "10.5"},
        ]
    }

    points = price_providers._parse_fmp_history(payload)

    assert points == [
        {"date": "2026-05-31", "value": 10.5},
        {"date": "2026-06-02", "value": 12.0},
    ]


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


def test_period_to_days_uses_daily_point_policy():
    assert price_providers._period_to_days("1d") == 7
    assert price_providers._period_to_days("1mo") == 30


def test_provider_date_normalization_accepts_rfc_and_iso_dates():
    assert price_providers._normalize_provider_date("Wed, 03 Jun 2026 00:00:01 +0000") == "2026-06-03"
    assert price_providers._normalize_provider_date("2026-06-04T00:00:01+00:00") == "2026-06-04"


def test_data_go_key_decodes_url_encoded_portal_key(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "DATA_GO_KR_API_KEY", "abc%2Bdef%3D%3D")

    params = price_providers._data_go_params({"numOfRows": 1})

    assert params["serviceKey"] == "abc+def=="


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
async def test_data_go_stock_history_sorts_before_period_limit(monkeypatch):
    rows = [
        {"basDt": "20260608", "clpr": "108"},
        {"basDt": "20260607", "clpr": "107"},
        {"basDt": "20260606", "clpr": "106"},
        {"basDt": "20260605", "clpr": "105"},
        {"basDt": "20260604", "clpr": "104"},
        {"basDt": "20260603", "clpr": "103"},
        {"basDt": "20260602", "clpr": "102"},
        {"basDt": "20260601", "clpr": "101"},
    ]

    async def fake_rows(url, params):
        return rows

    monkeypatch.setattr(price_providers, "_fetch_data_go_rows", fake_rows)

    payload = await price_providers.fetch_data_go_stock_history("005930.KS", "1d")

    assert [point["date"] for point in payload["points"]] == [
        "2026-06-02",
        "2026-06-03",
        "2026-06-04",
        "2026-06-05",
        "2026-06-06",
        "2026-06-07",
        "2026-06-08",
    ]
    assert payload["points"][0]["value"] == 102.0
    assert payload["provider_meta"]["provider"] == "data_go_kr"


@pytest.mark.asyncio
async def test_coingecko_history_requires_demo_key(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "COINGECKO_DEMO_API_KEY", None)

    payload = await price_providers.fetch_coingecko_history("BTC-USD", "1mo")

    assert payload["points"] == []
    assert payload["legacy"] == []


@pytest.mark.asyncio
async def test_fmp_history_requires_key_and_degrades(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "FMP_API_KEY", None)

    payload = await price_providers.fetch_fmp_history("^GSPC", "1mo")

    assert payload["points"] == []
    assert payload["legacy"] == []
    assert payload["provider_meta"]["provider"] == "fmp"
    assert payload["provider_meta"]["freshness"] == "missing_key"


@pytest.mark.asyncio
async def test_fmp_history_success_normalization(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "FMP_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "FMP_DAILY_CALL_BUDGET", 180)
    monkeypatch.setattr(price_providers.settings, "FMP_FETCH_TIMEOUT_SECONDS", 10)
    captured = {}

    async def fake_get_json(provider, url, *, params=None, headers=None, timeout=10.0):
        captured["provider"] = provider
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return {
            "historical": [
                {"date": "2026-06-01", "close": 100},
                {"date": "2026-06-02", "close": 105},
            ]
        }

    monkeypatch.setattr(price_providers, "_get_json", fake_get_json)

    payload = await price_providers.fetch_fmp_history("^GSPC", "1mo")

    assert captured["provider"] == "fmp"
    assert captured["url"].endswith("/historical-price-eod/full")
    assert captured["params"]["symbol"] == "^GSPC"
    assert captured["params"]["apikey"] == "test-key"
    assert captured["timeout"] == 10.0
    assert price_providers._fmp_daily_call_count == 1
    assert payload["points"] == [
        {"date": "2026-06-01", "value": 100.0},
        {"date": "2026-06-02", "value": 105.0},
    ]
    assert payload["provider_meta"]["provider"] == "fmp"
    assert payload["provider_meta"]["freshness"] == "eod_or_delayed"


@pytest.mark.asyncio
async def test_ndx_history_uses_stooq_without_global_optin(monkeypatch):
    # ^NDX는 FMP가 지수를 못 주므로 ENABLE_STOOQ_FALLBACK이 꺼져 있어도 Stooq를 1차로 쓴다.
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", False)
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "STOOQ_FETCH_TIMEOUT_SECONDS", 12)
    captured = {}

    async def fail_fmp(*args, **kwargs):
        raise AssertionError("FMP should not be called for ^NDX primary path")

    async def fake_get_stooq_text(params, *, timeout=10.0):
        captured["params"] = params
        return "Date,Open,High,Low,Close,Volume\n2026-06-01,1,2,1,19000,100\n2026-06-02,1,2,1,19500,100\n"

    monkeypatch.setattr(price_providers, "fetch_fmp_history", fail_fmp)
    monkeypatch.setattr(price_providers, "_get_stooq_text", fake_get_stooq_text)

    payload = await price_providers.fetch_market_history("^NDX", "1mo")

    assert captured["params"]["s"] == "^ndq"
    assert captured["params"]["apikey"] == "test-key"
    assert payload["points"] == [
        {"date": "2026-06-01", "value": 19000.0},
        {"date": "2026-06-02", "value": 19500.0},
    ]
    assert payload["provider_meta"]["provider"] == "stooq"


@pytest.mark.asyncio
async def test_ndx_snapshot_uses_stooq_without_global_optin(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", False)
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "STOOQ_FETCH_TIMEOUT_SECONDS", 12)

    async def fail_fmp_snapshot(*args, **kwargs):
        raise AssertionError("FMP snapshot should not be called for ^NDX primary path")

    async def fake_get_stooq_text(params, *, timeout=10.0):
        return "Date,Open,High,Low,Close,Volume\n2026-06-01,1,2,1,19000,100\n2026-06-02,1,2,1,19500,100\n"

    monkeypatch.setattr(price_providers, "_fetch_fmp_snapshot", fail_fmp_snapshot)
    monkeypatch.setattr(price_providers, "_get_stooq_text", fake_get_stooq_text)

    payload = await price_providers.fetch_market_snapshot("^NDX", "INDEX")

    assert payload["currentPrice"] == 19500.0
    assert payload["provider_meta"]["provider"] == "stooq"
    assert payload["provider_meta"]["symbol"] == "^ndq"


@pytest.mark.asyncio
async def test_ndx_stooq_requires_key(monkeypatch):
    # 키가 없으면 ^NDX도 Stooq를 호출하지 않고 빈 history로 degrade한다.
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", False)
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", None)

    async def fail_get_stooq_text(*args, **kwargs):
        raise AssertionError("Stooq should not be called without a key")

    monkeypatch.setattr(price_providers, "_get_stooq_text", fail_get_stooq_text)

    payload = await price_providers.fetch_stooq_history("^NDX", "1mo")

    assert payload["points"] == []


@pytest.mark.asyncio
async def test_fmp_daily_budget_exceeded_skips_provider_call(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "FMP_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "FMP_DAILY_CALL_BUDGET", 0)

    async def fail_get_json(*args, **kwargs):
        raise AssertionError("FMP provider should not be called when budget is 0")

    monkeypatch.setattr(price_providers, "_get_json", fail_get_json)

    payload = await price_providers.fetch_fmp_history("AAPL", "1mo")

    assert payload["points"] == []
    assert payload["provider_meta"]["freshness"] == "unavailable"
    assert price_providers._fmp_daily_call_count == 0


@pytest.mark.asyncio
async def test_fmp_empty_history_uses_failed_call_cooldown(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "FMP_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "FMP_DAILY_CALL_BUDGET", 180)
    calls = {"count": 0}

    async def fake_get_json(provider, url, *, params=None, headers=None, timeout=10.0):
        calls["count"] += 1
        return {"historical": []}

    monkeypatch.setattr(price_providers, "_get_json", fake_get_json)

    first = await price_providers.fetch_fmp_history("AAPL", "1mo")
    second = await price_providers.fetch_fmp_history("AAPL", "1mo")

    assert first["points"] == []
    assert second["points"] == []
    assert second["provider_meta"]["freshness"] == "cooldown"
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_market_history_uses_ticker_period_cache(monkeypatch):
    calls = {"count": 0}

    async def fake_fmp_history(ticker, period):
        calls["count"] += 1
        return {
            "ticker": ticker,
            "series_type": "price",
            "unit": "USD",
            "points": [{"date": "2026-06-02", "value": 100.0}],
            "legacy": [{"date": "2026-06-02", "close": 100.0, "value": 100.0}],
        }

    monkeypatch.setattr(price_providers, "fetch_fmp_history", fake_fmp_history)

    first = await price_providers.fetch_market_history("AAPL", "1mo")
    second = await price_providers.fetch_market_history("AAPL", "1mo")

    assert first == second
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_fx_snapshot_change_percent_from_stooq_close(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", True)

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
    assert snapshot["provider_meta"]["change_source"] == "stooq_fallback"


@pytest.mark.asyncio
async def test_fx_snapshot_falls_back_when_stooq_empty(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", True)

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
async def test_fx_snapshot_keeps_open_rate_without_stooq_fallback(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", False)
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", None)

    async def fake_get_json(provider, url, **kwargs):
        return {"rates": {"KRW": 1386.0}, "provider": "open.er-api.com"}

    async def fail_stooq_history(ticker, period):
        raise AssertionError("Stooq must not be called without fallback flag or key")

    monkeypatch.setattr(price_providers, "_get_json", fake_get_json)
    monkeypatch.setattr(price_providers, "fetch_stooq_history", fail_stooq_history)

    snapshot = await price_providers._fetch_fx_snapshot("KRW=X")

    assert snapshot["currentPrice"] == 1386.0
    assert snapshot["changePercent"] == 0.0
    assert snapshot["history_prices"] == [1386.0]
    assert snapshot["provider_meta"]["change_source"] == "none"


@pytest.mark.asyncio
async def test_fx_snapshot_uses_stooq_when_key_present_without_global_optin(monkeypatch):
    # A안: STOOQ_API_KEY만 있으면 ENABLE_STOOQ_FALLBACK이 꺼져 있어도 USD/KRW 등락을 계산한다.
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", False)
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "STOOQ_FETCH_TIMEOUT_SECONDS", 12)

    async def fake_get_json(provider, url, **kwargs):
        return {"rates": {"KRW": 1390.0}, "provider": "open.er-api.com"}

    async def fake_get_stooq_text(params, *, timeout=10.0):
        assert params["s"] == "usdkrw"
        assert params["apikey"] == "test-key"
        return "Date,Open,High,Low,Close,Volume\n2026-06-02,1,2,1,1370,100\n2026-06-03,1,2,1,1380,100\n"

    monkeypatch.setattr(price_providers, "_get_json", fake_get_json)
    monkeypatch.setattr(price_providers, "_get_stooq_text", fake_get_stooq_text)

    snapshot = await price_providers._fetch_fx_snapshot("KRW=X")

    # live rate(1390) vs stooq 최신 종가(1380) → 약 +0.7246%, 0이 아니다.
    assert snapshot["currentPrice"] == 1390.0
    assert snapshot["changePercent"] == round(((1390.0 - 1380.0) / 1380.0) * 100, 6)
    assert snapshot["changePercent"] != 0.0
    assert snapshot["provider_meta"]["change_source"] == "stooq_fallback"


@pytest.mark.asyncio
async def test_fx_snapshot_avoids_self_comparison_when_open_rate_missing(monkeypatch):
    # open.er-api가 비면 현재가를 stooq 최신 종가([-1])로 채우되, 전일 종가는 직전 종가([-2])로
    # 잡아 같은 값과 비교해 등락이 0으로 고착되는 경로를 막는다.
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", False)
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", "test-key")

    async def fake_get_json(provider, url, **kwargs):
        return {"rates": {}, "provider": "open.er-api.com"}

    async def fake_stooq_history(ticker, period):
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

    assert snapshot["currentPrice"] == 1380.0
    assert snapshot["changePercent"] == round(((1380.0 - 1370.0) / 1370.0) * 100, 6)
    assert snapshot["changePercent"] != 0.0
    assert snapshot["provider_meta"]["change_source"] == "stooq_fallback"


@pytest.mark.asyncio
async def test_fx_history_fallback_normalizes_open_er_api_rfc_date(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", False)
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", None)

    async def fake_fx_snapshot(ticker):
        return {
            "currentPrice": 1386.0,
            "provider_meta": {
                "provider": "open.er-api.com",
                "as_of": "Wed, 03 Jun 2026 00:00:01 +0000",
                "freshness": "daily_reference",
                "change_source": "none",
            },
        }

    monkeypatch.setattr(price_providers, "_fetch_fx_snapshot", fake_fx_snapshot)

    payload = await price_providers.fetch_market_history("KRW=X", "1d")

    assert payload["points"] == [{"date": "2026-06-03", "value": 1386.0}]
    assert payload["provider_meta"]["provider"] == "open.er-api.com"


@pytest.mark.asyncio
async def test_stooq_history_uses_configured_timeout(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", True)
    monkeypatch.setattr(price_providers.settings, "STOOQ_FETCH_TIMEOUT_SECONDS", 20)
    captured = {}

    async def fake_get_stooq_text(params, *, timeout=10.0):
        captured["params"] = params
        captured["timeout"] = timeout
        return "Date,Open,High,Low,Close,Volume\n2026-06-02,1,2,1,12,100\n"

    monkeypatch.setattr(price_providers, "_get_stooq_text", fake_get_stooq_text)

    payload = await price_providers.fetch_stooq_history("^GSPC", "1mo")

    assert captured["params"]["s"] == "^spx"
    assert captured["timeout"] == 20.0
    assert payload["points"] == [{"date": "2026-06-02", "value": 12.0}]


@pytest.mark.asyncio
async def test_stooq_history_returns_stale_cache_when_refresh_fails(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", True)
    cache_key = "stooq:^GSPC:1mo"
    stale_payload = price_providers._history_payload(
        "^GSPC",
        [{"date": "2026-06-01", "value": 5300.0}],
    )
    price_providers._history_cache[cache_key] = (
        price_providers.monotonic() - price_providers.HISTORY_CACHE_TTL_SECONDS - 1,
        stale_payload,
    )

    async def failing_get_stooq_text(*args, **kwargs):
        raise TimeoutError("stooq timeout")

    monkeypatch.setattr(price_providers, "_get_stooq_text", failing_get_stooq_text)

    payload = await price_providers.fetch_stooq_history("^GSPC", "1mo")

    assert payload == stale_payload


@pytest.mark.asyncio
async def test_stooq_history_disabled_by_default(monkeypatch):
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", False)

    async def fail_get_stooq_text(*args, **kwargs):
        raise AssertionError("Stooq provider should not be called by default")

    monkeypatch.setattr(price_providers, "_get_stooq_text", fail_get_stooq_text)

    payload = await price_providers.fetch_stooq_history("^GSPC", "1mo")

    assert payload["points"] == []
    assert payload["legacy"] == []


@pytest.mark.asyncio
async def test_stooq_history_does_not_cache_empty_result(monkeypatch):
    # 빈 파싱 결과를 12h 캐시에 넣으면 일시적 실패가 종일 0으로 고착된다.
    # 빈 결과는 캐시하지 않고 다음 호출이 곧바로 live 재시도하도록 둔다.
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", True)
    cache_key = "stooq:^NDX:1mo"

    async def empty_get_stooq_text(params, *, timeout=10.0):
        return "Get your apikey: open stooq"

    monkeypatch.setattr(price_providers, "_get_stooq_text", empty_get_stooq_text)

    payload = await price_providers.fetch_stooq_history("^NDX", "1mo")

    assert payload["points"] == []
    # 핵심: 빈 payload가 12h 히스토리 캐시에 남지 않아야 한다.
    assert cache_key not in price_providers._history_cache


@pytest.mark.asyncio
async def test_stooq_history_reuses_last_good_when_parse_empties(monkeypatch):
    # 직전 유효값이 있으면 빈 파싱 시 그 값을 유지한다(0으로 떨어뜨리지 않음).
    monkeypatch.setattr(price_providers.settings, "STOOQ_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", True)
    cache_key = "stooq:^NDX:1mo"
    good = price_providers._history_payload("^NDX", [{"date": "2026-06-09", "value": 29500.0}])
    price_providers._history_cache[cache_key] = (
        price_providers.monotonic() - price_providers.HISTORY_CACHE_TTL_SECONDS - 1,
        good,
    )

    async def empty_get_stooq_text(params, *, timeout=10.0):
        return "Get your apikey: open stooq"

    monkeypatch.setattr(price_providers, "_get_stooq_text", empty_get_stooq_text)

    payload = await price_providers.fetch_stooq_history("^NDX", "1mo")

    assert payload["points"] == [{"date": "2026-06-09", "value": 29500.0}]


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
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", True)
    monkeypatch.setattr(price_providers, "_get_json", fake_get_json)
    monkeypatch.setattr(price_providers, "_fetch_finnhub_profile_market_cap", failing_market_cap)
    monkeypatch.setattr(price_providers, "_fetch_fmp_profile_market_cap", failing_market_cap)
    monkeypatch.setattr(price_providers, "fetch_fmp_history", failing_stooq_history)
    monkeypatch.setattr(price_providers, "fetch_stooq_history", failing_stooq_history)

    snapshot = await price_providers._fetch_finnhub_stock_snapshot("NVDA")

    assert snapshot["currentPrice"] == 125.5
    assert snapshot["changePercent"] == 4.58
    assert snapshot["marketCap"] == 0.0
    assert snapshot["history_prices"] == [125.5]


@pytest.mark.asyncio
async def test_finnhub_stock_snapshot_falls_back_to_fmp_quote_when_finnhub_502(monkeypatch):
    # Finnhub /quote가 502로 실패해도 FMP quote로 현재가를 채워야 한다(가격 0 회피).
    async def failing_get_json(provider, url, **kwargs):
        assert provider == "finnhub"
        raise RuntimeError("502 Bad Gateway")

    async def fake_fmp_quote(symbol):
        assert symbol == "NVDA"
        return {
            "currentPrice": 130.0,
            "changePercent": 2.5,
            "history_prices": [130.0],
            "marketCap": 3.0e12,
        }

    async def failing_market_cap(symbol):
        raise TimeoutError("profile timeout")

    async def failing_history(ticker, period):
        raise TimeoutError("history timeout")

    monkeypatch.setattr(price_providers.settings, "FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", False)
    monkeypatch.setattr(price_providers, "_get_json", failing_get_json)
    monkeypatch.setattr(price_providers, "_fetch_fmp_quote_snapshot", fake_fmp_quote)
    monkeypatch.setattr(price_providers, "_fetch_finnhub_profile_market_cap", failing_market_cap)
    monkeypatch.setattr(price_providers, "_fetch_fmp_profile_market_cap", failing_market_cap)
    monkeypatch.setattr(price_providers, "fetch_fmp_history", failing_history)

    snapshot = await price_providers._fetch_finnhub_stock_snapshot("NVDA")

    assert snapshot["currentPrice"] == 130.0
    assert snapshot["changePercent"] == 2.5
    # finnhub/FMP profile이 모두 실패하면 FMP quote의 marketCap을 tertiary로 사용한다.
    assert snapshot["marketCap"] == 3.0e12
    assert snapshot["history_prices"] == [130.0]


@pytest.mark.asyncio
async def test_finnhub_stock_snapshot_falls_back_to_history_last_close(monkeypatch):
    # quote 계열(Finnhub·FMP)이 모두 비면 history의 마지막 종가로 현재가를 채운다.
    async def failing_get_json(provider, url, **kwargs):
        raise RuntimeError("502 Bad Gateway")

    async def empty_fmp_quote(symbol):
        return dict(price_providers.DEFAULT_RESPONSE)

    async def failing_market_cap(symbol):
        raise TimeoutError("profile timeout")

    async def fake_history(ticker, period):
        return price_providers._history_payload(
            "NVDA",
            [
                {"date": "2026-06-06", "value": 118.0},
                {"date": "2026-06-07", "value": 120.0},
            ],
        )

    monkeypatch.setattr(price_providers.settings, "FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(price_providers.settings, "ENABLE_STOOQ_FALLBACK", False)
    monkeypatch.setattr(price_providers, "_get_json", failing_get_json)
    monkeypatch.setattr(price_providers, "_fetch_fmp_quote_snapshot", empty_fmp_quote)
    monkeypatch.setattr(price_providers, "_fetch_finnhub_profile_market_cap", failing_market_cap)
    monkeypatch.setattr(price_providers, "_fetch_fmp_profile_market_cap", failing_market_cap)
    monkeypatch.setattr(price_providers, "fetch_fmp_history", fake_history)

    snapshot = await price_providers._fetch_finnhub_stock_snapshot("NVDA")

    assert snapshot["currentPrice"] == 120.0
    assert snapshot["changePercent"] == round(((120.0 - 118.0) / 118.0) * 100, 6)
    assert snapshot["history_prices"] == [118.0, 120.0]


@pytest.mark.asyncio
async def test_market_snapshot_keeps_stale_when_live_returns_no_price(monkeypatch):
    # 전 provider 실패로 현재가가 0이면 직전 유효 스냅샷(stale)을 유지해야 한다.
    cache_key = "snapshot:STOCK_US:NVDA"
    good = {
        "currentPrice": 121.0,
        "changePercent": 1.0,
        "history_prices": [121.0],
        "marketCap": 1.0,
    }
    # TTL이 지난(stale) 타임스탬프로 심어 _cache_get은 miss → live fetch로 진입하게 한다.
    price_providers._snapshot_cache[cache_key] = (
        price_providers.monotonic() - price_providers.SNAPSHOT_CACHE_TTL_SECONDS - 1,
        good,
    )

    async def zero_snapshot(symbol):
        return dict(price_providers.DEFAULT_RESPONSE)

    monkeypatch.setattr(price_providers, "_fetch_finnhub_stock_snapshot", zero_snapshot)

    snapshot = await price_providers.fetch_market_snapshot("NVDA", "STOCK_US")

    assert snapshot == good
    # stale 경로는 last-good 값을 다시 캐시에 적어 다음 TTL 윈도까지 제공한다.
    assert price_providers._snapshot_cache[cache_key][1] == good


@pytest.mark.asyncio
async def test_market_snapshot_does_not_cache_zero_price_without_stale(monkeypatch):
    # 직전 유효값이 없으면 0을 반환하되, 캐시에 0을 덮어써 고착시키지 않는다.
    async def zero_snapshot(symbol):
        return dict(price_providers.DEFAULT_RESPONSE)

    monkeypatch.setattr(price_providers, "_fetch_finnhub_stock_snapshot", zero_snapshot)

    snapshot = await price_providers.fetch_market_snapshot("NVDA", "STOCK_US")

    assert snapshot["currentPrice"] == 0.0
    assert "snapshot:STOCK_US:NVDA" not in price_providers._snapshot_cache


@pytest.mark.asyncio
async def test_market_price_collection_mocks_non_live_tickers(monkeypatch):
    monkeypatch.setattr(market_service.settings, "MARKET_LIVE_TICKERS", "NVDA")

    async def fail_fetch_asset_data(*args, **kwargs):
        raise AssertionError("non-live ticker should not call a provider")

    monkeypatch.setattr(market_service, "fetch_asset_data", fail_fetch_asset_data)

    group_name, results = await market_service._collect_prices_group(
        "us_top10",
        {"AAPL": {"ticker": "AAPL", "category": "STOCK_US"}},
    )

    assert group_name == "us_top10"
    assert results["AAPL"]["symbol"] == "AAPL"
    assert results["AAPL"]["price"] > 0
    assert len(results["AAPL"]["history_prices"]) == 30


@pytest.mark.asyncio
async def test_market_price_collection_keeps_live_tickers_on_provider_path(monkeypatch):
    monkeypatch.setattr(market_service.settings, "MARKET_LIVE_TICKERS", "NVDA")
    calls = {"count": 0}

    async def fake_fetch_asset_data(ticker, category):
        calls["count"] += 1
        return {
            "currentPrice": 125.0,
            "changePercent": 1.5,
            "history_prices": [124.0, 125.0],
            "marketCap": 1.0,
        }

    monkeypatch.setattr(market_service, "fetch_asset_data", fake_fetch_asset_data)

    _, results = await market_service._collect_prices_group(
        "us_top10",
        {"NVDA": {"ticker": "NVDA", "category": "STOCK_US"}},
    )

    assert calls["count"] == 1
    assert results["NVDA"]["price"] == 125.0


@pytest.mark.asyncio
async def test_market_news_collection_mocks_non_live_tickers(monkeypatch):
    monkeypatch.setattr(market_service.settings, "MARKET_LIVE_TICKERS", "NVDA")

    async def fail_news_items(*args, **kwargs):
        raise AssertionError("non-live ticker should not call a news provider")

    monkeypatch.setattr(market_service, "fetch_market_news_items", fail_news_items)

    _, results = await market_service._collect_news_group("us_top10", {"AAPL": "AAPL"})

    assert results["AAPL"]["symbol"] == "AAPL"
    assert results["AAPL"]["items"][0]["source"] == "demo_mock"


@pytest.mark.asyncio
async def test_latest_context_force_refresh_respects_cooldown(monkeypatch):
    monkeypatch.setattr(market_service.settings, "MARKET_LIVE_TICKERS", "AAPL")
    calls = {"count": 0}

    async def fake_context(ticker):
        calls["count"] += 1
        return {"news": [{"title": "A", "link": "", "source": "test"}], "events": []}

    monkeypatch.setattr(market_service, "fetch_latest_provider_context", fake_context)

    first = await market_service.fetch_latest_asset_context("AAPL", force_refresh=True)
    second = await market_service.fetch_latest_asset_context("AAPL", force_refresh=True)

    assert first == second
    assert calls["count"] == 1

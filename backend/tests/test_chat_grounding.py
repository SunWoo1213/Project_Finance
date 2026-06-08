import pytest

from app.core.cache import market_cache
from app.services import chat_grounding


@pytest.fixture
def seeded_cache():
    original_prices = market_cache.get("prices")
    original_updated = market_cache.get("last_updated")
    market_cache["prices"] = {
        "macro": {
            "S&P 500": {"symbol": "^GSPC", "price": 5500.0, "changePercent": 1.25},
            "USDKRW": {"symbol": "KRW=X", "close": 1380.5, "change_pct": -0.4},
        },
        "us_top10": {
            "TSLA": {"symbol": "TSLA", "currentPrice": 250.0, "changePercent": 2.0},
        },
        "kr_top10": {
            "삼성전자": {"symbol": "005930.KS", "price": 80000, "change_pct": 0.5},
        },
    }
    market_cache["last_updated"] = {"prices": "2026-06-08T09:00:00+00:00"}
    yield
    market_cache["prices"] = original_prices
    market_cache["last_updated"] = original_updated


def test_asset_snapshot_absorbs_key_drift(seeded_cache):
    # `close` + `change_pct` keys still resolve to price/change_pct.
    snap = chat_grounding.asset_snapshot("KRW=X")
    assert snap is not None
    assert snap["price"] == 1380.5
    assert snap["change_pct"] == -0.4
    assert snap["currency"] == "KRW"
    assert snap["as_of"] == "2026-06-08T09:00:00+00:00"


def test_asset_snapshot_currentprice_and_currency(seeded_cache):
    snap = chat_grounding.asset_snapshot("TSLA")
    assert snap["price"] == 250.0
    assert snap["currency"] == "USD"


def test_asset_snapshot_unknown_ticker_returns_none(seeded_cache):
    assert chat_grounding.asset_snapshot("NOPE") is None


def test_asset_snippet_includes_currency_and_as_of(seeded_cache):
    snippet = chat_grounding.asset_snippet("005930.KS")
    assert "삼성전자" in snippet
    assert "KRW" in snippet
    assert "2026-06-08" in snippet


def test_macro_overview_lines(seeded_cache):
    lines, updated = chat_grounding.macro_overview_lines()
    assert any("S&P 500" in line for line in lines)
    assert updated == "2026-06-08T09:00:00+00:00"


def test_guard_passes_when_numbers_are_grounded(seeded_cache):
    grounding = {"market_snippet": chat_grounding.asset_snippet("TSLA"), "quotes": [chat_grounding.asset_snapshot("TSLA")]}
    result = chat_grounding.guard_answer("테슬라는 +2.00% 상승했고 가격은 250.0 입니다.", grounding)
    assert result.grounded is True


def test_guard_flags_ungrounded_number():
    grounding = {"market_snippet": "테슬라 가격 250.0 +2.00%"}
    result = chat_grounding.guard_answer("테슬라는 무려 +9.99% 급등했습니다.", grounding)
    assert result.grounded is False
    assert "9.99" in result.ungrounded


def test_guard_ignores_bare_integers():
    # "10년물", "TOP10", "3문장" style integers must never be flagged.
    grounding = {"market_snippet": "미국 10년물 국채"}
    result = chat_grounding.guard_answer("미국 10년물 국채는 TOP10 자산이며 3문장으로 정리했습니다.", grounding)
    assert result.grounded is True

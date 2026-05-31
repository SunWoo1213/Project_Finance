import pytest
from fastapi import HTTPException

from app import main
from app.core.cache import market_cache
from app.models import AIReport, Asset, AssetCategory
from app.services import ai_service, external_api_service
from app.services.graph.graph import route_fact_check
from app.services.graph.nodes import fact_checker_node


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDbSession:
    def __init__(self, asset=None):
        self.asset = asset
        self.execute_calls = 0
        self.added = []
        self.flushed = False
        self.committed = False

    async def execute(self, query):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return ScalarResult("")
        return ScalarResult(self.asset)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushed = True

    async def commit(self):
        self.committed = True


class FakeGraph:
    def __init__(self, result):
        self.result = result
        self.received_state = None

    async def ainvoke(self, state, config=None):
        self.received_state = state
        return self.result


@pytest.fixture
def cached_aapl(monkeypatch):
    monkeypatch.setitem(
        market_cache,
        "prices",
        {
            "us_top10": {
                "AAPL": {
                    "symbol": "AAPL",
                    "price": 200.0,
                    "change_pct": 1.25,
                }
            }
        },
    )
    monkeypatch.setitem(
        market_cache,
        "news",
        {
            "us_top10": {
                "AAPL": {
                    "symbol": "AAPL",
                    "items": [
                        {
                            "title": "Apple expands services revenue",
                            "link": "https://example.com/aapl-services",
                            "source": "Example News",
                        }
                    ],
                }
            }
        },
    )
    monkeypatch.setitem(
        market_cache,
        "last_updated",
        {
            "prices": "2026-05-30T00:00:00+00:00",
            "news": "2026-05-30T00:05:00+00:00",
            "latest_context": {},
        },
    )

    async def fake_latest_context(ticker):
        return {
            "ticker": ticker,
            "symbol": ticker,
            "fetched_at": "2026-05-30T00:10:00+00:00",
            "source": "test",
            "source_status": "fresh",
            "news": [],
            "events": [],
        }

    monkeypatch.setattr(ai_service, "fetch_latest_asset_context", fake_latest_context)


@pytest.mark.asyncio
async def test_generate_report_saves_only_when_evaluator_passes(monkeypatch, cached_aapl):
    graph = FakeGraph(
        {
            "is_pass": True,
            "feedback": "PASS",
            "fact_check_pass": True,
            "fact_check_feedback": "",
            "revision_count": 1,
            "analysis_result": "draft",
            "final_report": "# final",
            "structured_facts": {
                "bull_factors": ["서비스 매출 성장"],
                "bear_factors": ["밸류에이션 부담"],
                "risk_factors": ["공급망 리스크"],
                "data_as_of": "2026-05-30T00:10:00+00:00",
            },
        }
    )
    monkeypatch.setattr(ai_service, "graph_app", graph)
    asset = Asset(id=1, ticker="AAPL", name="AAPL", category=AssetCategory.STOCK_US)
    db = FakeDbSession(asset=asset)

    result = await ai_service.generate_report_for_ticker("AAPL", db)

    assert db.committed is True
    assert db.flushed is True
    assert isinstance(db.added[0], AIReport)
    assert "서비스 매출 성장" in db.added[0].bull_summary
    assert "밸류에이션 부담" in db.added[0].bear_summary
    assert result["generation_metadata"]["is_pass"] is True
    assert result["generation_metadata"]["fact_check_pass"] is True
    assert "공급망 리스크" in result["generation_metadata"]["risk_summary"]
    assert graph.received_state["report_facts"]["price"]["value"] == 200.0
    assert graph.received_state["report_facts"]["requirements"]["required"]
    assert "market_cap" in graph.received_state["report_facts"]["missing_required_facts"]
    assert graph.received_state["financial_facts"] == {}


@pytest.mark.asyncio
async def test_generate_report_rejects_failed_evaluation_without_saving(monkeypatch, cached_aapl):
    graph = FakeGraph(
        {
            "is_pass": False,
            "feedback": "Unsupported numbers remain",
            "revision_count": 3,
            "analysis_result": "draft",
            "final_report": "# final",
            "structured_facts": {},
        }
    )
    monkeypatch.setattr(ai_service, "graph_app", graph)
    db = FakeDbSession(asset=Asset(id=1, ticker="AAPL", name="AAPL", category=AssetCategory.STOCK_US))

    with pytest.raises(ai_service.ReportQualityError) as exc_info:
        await ai_service.generate_report_for_ticker("AAPL", db)

    assert "Unsupported numbers remain" in exc_info.value.feedback
    assert exc_info.value.revision_count == 3
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_report_generation_policy_rejects_missing_user():
    with pytest.raises(HTTPException) as exc_info:
        main.ensure_report_generation_allowed(None)

    assert exc_info.value.status_code == 401


def test_fact_checker_passes_when_numbers_exist_in_structured_facts():
    result = fact_checker_node(
        {
            "ticker": "AAPL",
            "draft_report": "현재 가격은 200달러이고 변동률은 1.25%입니다.",
            "report_facts": {
                "price": {"value": 200.0, "change_pct": 1.25, "as_of": "2026-05-30T00:00:00+00:00"}
            },
            "structured_facts": {},
            "financial_facts": {},
            "news_facts": {},
            "macro_facts": {},
            "feedback": "",
            "revision_count": 0,
            "retry_count": 0,
        }
    )

    assert result["fact_check_pass"] is True
    assert result["fact_check_feedback"] == ""


def test_fact_checker_rejects_unsupported_numbers_and_routes_to_writer():
    state = {
        "ticker": "AAPL",
        "draft_report": "현재 가격은 999달러이고 변동률은 1.25%입니다.",
        "report_facts": {"price": {"value": 200.0, "change_pct": 1.25}},
        "structured_facts": {},
        "financial_facts": {},
        "news_facts": {},
        "macro_facts": {},
        "feedback": "",
        "revision_count": 0,
        "retry_count": 0,
    }
    result = fact_checker_node(state)

    assert result["fact_check_pass"] is False
    assert "999" in result["fact_check_feedback"]
    assert result["revision_count"] == 1
    assert route_fact_check({**state, **result}) == "writer_node"


def test_fact_checker_routes_to_end_after_revision_limit():
    state = {
        "ticker": "AAPL",
        "draft_report": "현재 가격은 999달러입니다.",
        "report_facts": {"price": {"value": 200.0}},
        "structured_facts": {},
        "financial_facts": {},
        "news_facts": {},
        "macro_facts": {},
        "feedback": "",
        "revision_count": 2,
        "retry_count": 2,
    }
    result = fact_checker_node(state)

    assert result["revision_count"] == 3
    assert route_fact_check({**state, **result}) == "END"


def test_build_report_facts_marks_asset_specific_limitations(monkeypatch):
    monkeypatch.setitem(
        market_cache,
        "last_updated",
        {
            "prices": "2026-05-30T00:00:00+00:00",
            "news": "2026-05-30T00:05:00+00:00",
            "latest_context": {},
        },
    )

    facts = ai_service._build_report_facts(
        "005930.KS",
        AssetCategory.STOCK_KR,
        {"symbol": "005930.KS", "price": 70000.0, "change_pct": -0.5},
        [],
        {
            "fetched_at": "2026-05-30T00:10:00+00:00",
            "source": "test",
            "source_status": "fresh",
            "events": [],
        },
    )

    assert facts["asset_category"] == "STOCK_KR"
    assert "company_news" in facts["missing_required_facts"]
    assert any("국내 개별주 재무제표" in item for item in facts["data_limitations"])


@pytest.mark.asyncio
async def test_structured_external_provider_reports_missing_key_without_network(monkeypatch):
    monkeypatch.setattr(external_api_service, "FMP_API_KEY", "")
    monkeypatch.setattr(external_api_service, "FINNHUB_API_KEY", "")

    fmp = await external_api_service.fetch_fmp_financials_structured("AAPL")
    finnhub = await external_api_service.fetch_finnhub_news_structured("AAPL")
    coingecko = await external_api_service.fetch_coingecko_data_structured("UNKNOWN-USD")

    assert fmp["status"] == "missing"
    assert finnhub["status"] == "missing"
    assert coingecko["status"] == "unsupported"
    assert fmp["limitations"]

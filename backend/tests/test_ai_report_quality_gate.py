import pytest
from fastapi import HTTPException

from app import main
from app.core.cache import market_cache
from app.models import AIReport, Asset, AssetCategory
from app.services import ai_service, external_api_service
from app.services.graph.graph import route_fact_check, route_format_check, route_qualitative_check
from app.services.graph.nodes import (
    EvaluationResult,
    StructuredFacts,
    _llm_with_flexible_structured_output,
    bear_agent_node,
    bull_agent_node,
    fact_checker_node,
    qualitative_claim_checker_node,
    report_format_validator_node,
    risk_officer_node,
)


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
            "format_check_pass": True,
            "format_check_feedback": "",
            "fact_check_pass": True,
            "fact_check_feedback": "",
            "qualitative_check_pass": True,
            "qualitative_check_feedback": "",
            "revision_count": 1,
            "analysis_result": "draft",
            "final_report": "# final",
            "structured_facts": {
                "analysis_framework": {"label": "US stock equity framework"},
                "bull_factors": ["서비스 매출 성장"],
                "bear_factors": ["밸류에이션 부담"],
                "risk_factors": ["공급망 리스크"],
                "data_as_of": "2026-05-30T00:10:00+00:00",
            },
            "bull_thesis": {"thesis": ["서비스 매출 성장"]},
            "bear_thesis": {"thesis": ["밸류에이션 부담"]},
            "risk_review": {"findings": ["공급망 리스크"]},
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
    assert result["generation_metadata"]["format_check_pass"] is True
    assert result["generation_metadata"]["fact_check_pass"] is True
    assert result["generation_metadata"]["qualitative_check_pass"] is True
    assert db.added[0].metadata_json["quality_status"] == "pass"
    assert result["generation_metadata"]["analysis_framework"]["label"] == "US stock equity framework"
    assert "공급망 리스크" in result["generation_metadata"]["risk_summary"]
    assert result["generation_metadata"]["role_outputs"]["bull_thesis"]["thesis"] == ["서비스 매출 성장"]
    assert graph.received_state["report_facts"]["price"]["value"] == 200.0
    assert graph.received_state["report_facts"]["requirements"]["required"]
    assert graph.received_state["report_facts"]["analysis_framework"]["label"] == "US stock equity framework"
    assert "market_cap" in graph.received_state["report_facts"]["missing_required_facts"]
    assert graph.received_state["financial_facts"] == {}
    assert graph.received_state["bull_thesis"] == {}
    assert graph.received_state["format_check_pass"] is False
    assert graph.received_state["qualitative_check_pass"] is False


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


@pytest.mark.asyncio
async def test_generate_report_blocks_when_readiness_is_insufficient(monkeypatch):
    monkeypatch.setitem(
        market_cache,
        "prices",
        {"us_top10": {"AAPL": {"symbol": "AAPL", "price": 0, "change_pct": 0}}},
    )
    monkeypatch.setitem(market_cache, "news", {"us_top10": {"AAPL": {"symbol": "AAPL", "items": []}}})
    monkeypatch.setitem(
        market_cache,
        "last_updated",
        {"prices": "2026-05-30T00:00:00+00:00", "news": "2026-05-30T00:05:00+00:00"},
    )

    async def fake_latest_context(ticker):
        return {"ticker": ticker, "source_status": "fresh", "news": [], "events": []}

    graph = FakeGraph({"is_pass": True})
    monkeypatch.setattr(ai_service, "fetch_latest_asset_context", fake_latest_context)
    monkeypatch.setattr(ai_service, "graph_app", graph)

    with pytest.raises(ai_service.ReportReadinessError) as exc_info:
        await ai_service.generate_report_for_ticker("AAPL", FakeDbSession())

    assert exc_info.value.metadata["quality_status"] == "blocked"
    assert graph.received_state is None


def test_report_generation_policy_rejects_manual_generation():
    with pytest.raises(HTTPException) as exc_info:
        main.ensure_report_generation_allowed(None)

    assert exc_info.value.status_code == 403
    assert "scheduler" in exc_info.value.detail


def test_flexible_structured_output_uses_function_calling(monkeypatch):
    class FakeLlm:
        def __init__(self):
            self.calls = []

        def with_structured_output(self, schema, **kwargs):
            self.calls.append((schema, kwargs))
            return "structured-llm"

    fake_llm = FakeLlm()
    monkeypatch.setattr("app.services.graph.nodes.get_llm", lambda: fake_llm)

    assert _llm_with_flexible_structured_output(StructuredFacts) == "structured-llm"
    assert _llm_with_flexible_structured_output(EvaluationResult) == "structured-llm"
    assert fake_llm.calls == [
        (StructuredFacts, {"method": "function_calling"}),
        (EvaluationResult, {"method": "function_calling"}),
    ]


def test_scheduled_report_jobs_detach_asset_values():
    assets = [
        Asset(id=1, ticker="DGS10", name="US 10Y Treasury", category=AssetCategory.BOND_US),
        Asset(id=2, ticker="BTC-USD", name="Bitcoin", category=AssetCategory.CRYPTO),
    ]

    assert ai_service._scheduled_report_jobs(assets) == [
        {"asset_id": 1, "ticker": "DGS10"},
        {"asset_id": 2, "ticker": "BTC-USD"},
    ]


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
    assert route_fact_check({"revision_count": 0, **result}) == "qualitative_claim_checker_node"


def test_report_format_validator_passes_fixed_template_sections():
    draft = """
## 1. 핵심 요약
## 2. 데이터 기준 시각과 한계
## 3. 가격과 시장 반응
## 4. Bull 시나리오
## 5. Bear 시나리오
## 6. 핵심 촉매
## 7. 주요 리스크
## 8. 자산군별 분석
## 9. 균형 결론
## 10. 투자 유의사항
"""
    state = {
        "ticker": "AAPL",
        "draft_report": draft,
        "feedback": "",
        "revision_count": 0,
        "retry_count": 0,
    }

    result = report_format_validator_node(state)

    assert result["format_check_pass"] is True
    assert result["format_check_feedback"] == ""
    assert route_format_check({**state, **result}) == "fact_checker_node"


def test_report_format_validator_passes_framework_topics():
    draft = """
## 1. 핵심 요약
## 2. 데이터 기준 시각과 한계
## 3. 가격과 시장 반응
## 4. Bull 시나리오
## 5. Bear 시나리오
## 6. 핵심 촉매
## 7. 주요 리스크
## 8. 자산군별 분석
- 가격과 거래량: 가격 데이터와 거래량 데이터 기준으로 단기 변동을 설명합니다.
- 유동성 환경: 유동성 데이터가 제한적이면 데이터 한계를 명시합니다.
- ETF와 규제 뉴스: 확인된 뉴스가 없으면 규제 촉매를 단정하지 않습니다.
## 9. 균형 결론
## 10. 투자 유의사항
"""
    state = {
        "ticker": "BTC-USD",
        "draft_report": draft,
        "report_facts": {
            "analysis_framework": {
                "required_sections": ["가격과 거래량", "유동성 환경", "ETF와 규제 뉴스"]
            }
        },
        "feedback": "",
        "revision_count": 0,
        "retry_count": 0,
    }

    result = report_format_validator_node(state)

    assert result["format_check_pass"] is True
    assert route_format_check({**state, **result}) == "fact_checker_node"


def test_report_format_validator_rejects_missing_framework_topics():
    draft = """
## 1. 핵심 요약
## 2. 데이터 기준 시각과 한계
## 3. 가격과 시장 반응
## 4. Bull 시나리오
## 5. Bear 시나리오
## 6. 핵심 촉매
## 7. 주요 리스크
## 8. 자산군별 분석
- 가격과 거래량: 가격 데이터 기준으로 단기 변동을 설명합니다.
## 9. 균형 결론
## 10. 투자 유의사항
"""
    state = {
        "ticker": "BTC-USD",
        "draft_report": draft,
        "report_facts": {
            "analysis_framework": {
                "required_sections": ["가격과 거래량", "유동성 환경", "ETF와 규제 뉴스"]
            }
        },
        "feedback": "",
        "revision_count": 0,
        "retry_count": 0,
    }

    result = report_format_validator_node(state)

    assert result["format_check_pass"] is False
    assert "유동성 환경" in result["format_check_feedback"]
    assert "ETF와 규제 뉴스" in result["format_check_feedback"]
    assert result["revision_count"] == 1
    assert route_format_check({**state, **result}) == "writer_node"


def test_report_format_validator_rejects_framework_topics_outside_asset_framework_section():
    draft = """
## 1. 핵심 요약
- 가격과 거래량: 본문 밖에서만 언급합니다.
- 유동성 환경: 본문 밖에서만 언급합니다.
## 2. 데이터 기준 시각과 한계
## 3. 가격과 시장 반응
## 4. Bull 시나리오
## 5. Bear 시나리오
## 6. 핵심 촉매
## 7. 주요 리스크
## 8. 자산군별 분석
이 섹션에는 실제 프레임워크 항목이 없습니다.
## 9. 균형 결론
## 10. 투자 유의사항
"""
    state = {
        "ticker": "BTC-USD",
        "draft_report": draft,
        "report_facts": {
            "analysis_framework": {
                "required_sections": ["가격과 거래량", "유동성 환경"]
            }
        },
        "feedback": "",
        "revision_count": 0,
        "retry_count": 0,
    }

    result = report_format_validator_node(state)

    assert result["format_check_pass"] is False
    assert "가격과 거래량" in result["format_check_feedback"]
    assert "유동성 환경" in result["format_check_feedback"]


def test_report_format_validator_rejects_label_only_framework_topics():
    draft = """
## 1. 핵심 요약
## 2. 데이터 기준 시각과 한계
## 3. 가격과 시장 반응
## 4. Bull 시나리오
## 5. Bear 시나리오
## 6. 핵심 촉매
## 7. 주요 리스크
## 8. 자산군별 분석
- 가격과 거래량
- 유동성 환경
## 9. 균형 결론
## 10. 투자 유의사항
"""
    state = {
        "ticker": "BTC-USD",
        "draft_report": draft,
        "report_facts": {
            "analysis_framework": {
                "required_sections": ["가격과 거래량", "유동성 환경"]
            }
        },
        "feedback": "",
        "revision_count": 0,
        "retry_count": 0,
    }

    result = report_format_validator_node(state)

    assert result["format_check_pass"] is False
    assert "가격과 거래량" in result["format_check_feedback"]


def test_report_format_validator_rejects_missing_fixed_headings_even_when_framework_words_match():
    draft = """
## 1. 핵심 요약
## 2. 데이터 기준 시각과 한계
## 4. Bull 시나리오
## 5. Bear 시나리오
## 6. 핵심 촉매
## 8. 자산군별 분석
- 가격과 거래량
- 리스크온/오프 심리
## 9. 균형 결론
## 10. 투자 유의사항
"""
    state = {
        "ticker": "BTC-USD",
        "draft_report": draft,
        "report_facts": {
            "analysis_framework": {
                "required_sections": ["가격과 거래량", "리스크온/오프 심리"]
            }
        },
        "feedback": "",
        "revision_count": 0,
        "retry_count": 0,
    }

    result = report_format_validator_node(state)

    assert result["format_check_pass"] is False
    assert "가격과 시장 반응" in result["format_check_feedback"]
    assert "주요 리스크" in result["format_check_feedback"]
    assert route_format_check({**state, **result}) == "writer_node"


def test_report_format_validator_rejects_missing_sections_and_routes_to_writer():
    state = {
        "ticker": "AAPL",
        "draft_report": "## 핵심 요약\n가격 설명만 있습니다.",
        "feedback": "",
        "revision_count": 0,
        "retry_count": 0,
    }

    result = report_format_validator_node(state)

    assert result["format_check_pass"] is False
    assert "자산군별 분석" in result["format_check_feedback"]
    assert result["revision_count"] == 1
    assert route_format_check({**state, **result}) == "writer_node"


def test_report_format_validator_routes_to_end_after_revision_limit():
    state = {
        "ticker": "AAPL",
        "draft_report": "## 핵심 요약\n불완전한 리포트입니다.",
        "feedback": "",
        "revision_count": 2,
        "retry_count": 2,
    }

    result = report_format_validator_node(state)

    assert result["revision_count"] == 3
    assert route_format_check({**state, **result}) == "END"


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


def test_qualitative_claim_checker_rejects_unsupported_high_risk_claims():
    state = {
        "ticker": "BTC-USD",
        "draft_report": "규제 완화 기대가 커지고 기관 수급이 강화되고 있습니다.",
        "report_facts": {},
        "structured_facts": {"news": [], "data_limitations": ["규제와 ETF 뉴스가 확인되지 않았습니다."]},
        "financial_facts": {},
        "news_facts": {},
        "macro_facts": {},
        "feedback": "",
        "revision_count": 0,
        "retry_count": 0,
    }

    result = qualitative_claim_checker_node(state)

    assert result["qualitative_check_pass"] is False
    assert "기관 수급" in result["qualitative_check_feedback"]
    assert route_qualitative_check({**state, **result}) == "writer_node"


def test_qualitative_claim_checker_passes_when_evidence_exists():
    state = {
        "ticker": "BTC-USD",
        "draft_report": "ETF 자금 유입이 단기 촉매로 작용할 수 있습니다.",
        "report_facts": {"news": [{"title": "Bitcoin ETF inflow rises"}]},
        "structured_facts": {"news": [{"title": "ETF 자금 유입이 증가했다는 보도"}]},
        "financial_facts": {},
        "news_facts": {},
        "macro_facts": {},
        "feedback": "",
        "revision_count": 0,
        "retry_count": 0,
    }

    result = qualitative_claim_checker_node(state)

    assert result["qualitative_check_pass"] is True
    assert route_qualitative_check({**state, **result}) == "evaluator_node"


def test_role_nodes_derive_separate_views_without_llm():
    state = {
        "ticker": "AAPL",
        "report_facts": {
            "missing_required_facts": ["market_cap"],
            "source_status": {"price": "cached"},
        },
        "structured_facts": {
            "bull_factors": ["서비스 매출 성장"],
            "bear_factors": ["밸류에이션 부담"],
            "risk_factors": ["공급망 리스크"],
            "data_limitations": ["시가총액 데이터가 비어 있습니다."],
            "news": [{"title": "Apple expands services revenue"}],
        },
    }

    bull = bull_agent_node(state)["bull_thesis"]
    bear = bear_agent_node(state)["bear_thesis"]
    risk = risk_officer_node(state)["risk_review"]

    assert bull["stance"] == "positive_scenario"
    assert bull["thesis"] == ["서비스 매출 성장"]
    assert bear["stance"] == "negative_scenario"
    assert bear["thesis"] == ["밸류에이션 부담"]
    assert risk["stance"] == "risk_and_uncertainty"
    assert "공급망 리스크" in risk["findings"]
    assert "market_cap" in risk["missing_required_facts"]


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
    assert facts["analysis_framework"]["label"] == "Korean stock local-market framework"
    assert "환율 민감도" in facts["analysis_framework"]["required_sections"]
    assert "company_news" in facts["missing_required_facts"]
    assert any("국내 개별주 재무제표" in item for item in facts["data_limitations"])


def test_build_report_facts_adds_crypto_framework(monkeypatch):
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
        "BTC-USD",
        AssetCategory.CRYPTO,
        {"symbol": "BTC-USD", "price": 68000.0, "change_pct": 1.1, "volume": 1000000},
        [{"title": "Bitcoin ETF flows rise", "source": "Example", "link": "https://example.com/btc"}],
        {
            "fetched_at": "2026-05-30T00:10:00+00:00",
            "source": "test",
            "source_status": "fresh",
            "events": [],
        },
    )

    assert facts["analysis_framework"]["label"] == "Crypto liquidity and regulation framework"
    assert "ETF와 규제 뉴스" in facts["analysis_framework"]["required_sections"]
    assert any("온체인" in rule for rule in facts["analysis_framework"]["interpretation_rules"])


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

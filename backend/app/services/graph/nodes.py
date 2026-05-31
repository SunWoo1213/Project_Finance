from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from ..external_api_service import (
    fetch_coingecko_data_structured,
    fetch_finnhub_news_structured,
    fetch_fmp_financials_structured,
    format_provider_facts,
)
from .llm import get_llm
from .state import AgentState
from .tools import tools

logger = logging.getLogger(__name__)

LANGUAGE_REQUIREMENT = """
[CRITICAL LANGUAGE REQUIREMENT]
최종 리포트는 반드시 완벽하고 전문적인 한국어(Korean)로 작성할 것.
불가피한 기술 용어/티커 심볼 외에는 영어 문장을 사용하지 말 것.
"""


class StructuredFacts(BaseModel):
    ticker: str = ""
    asset_category: str = ""
    price: dict[str, Any] = Field(default_factory=dict)
    valuation: list[dict[str, Any] | str] = Field(default_factory=list)
    financials: list[dict[str, Any] | str] = Field(default_factory=list)
    news: list[dict[str, Any] | str] = Field(default_factory=list)
    macro: list[dict[str, Any] | str] = Field(default_factory=list)
    events: list[dict[str, Any] | str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    source_status: dict[str, Any] = Field(default_factory=dict)
    data_as_of: str = ""
    key_numbers: list[str] = Field(default_factory=list)
    market_sentiment_news: list[str] = Field(default_factory=list)
    bull_factors: list[str] = Field(default_factory=list)
    bear_factors: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    summary: str = ""


class EvaluationResult(BaseModel):
    is_pass: bool = Field(description="리포트가 배포 가능한 품질이면 true")
    feedback: str = Field(description="개선 피드백")


NUMERIC_TOKEN_PATTERN = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?%?")


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _run_research_agent(title: str, instructions: str, query: str) -> str:
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_year = now.year
    llm = get_llm()
    prompt = f"""
[Role]
{title}

[Date]
오늘 날짜는 {current_date}입니다.
반드시 {current_year}년 기준 최신 정보를 우선 탐색하세요.

[Instructions]
{instructions}
"""
    agent = create_react_agent(llm, tools=tools, prompt=prompt)
    result = agent.invoke({"messages": [("user", query)]})
    return result["messages"][-1].content


def _normalize_numeric_token(value: Any) -> str | None:
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace(",", "").replace("%", "").replace("+", "")
    try:
        number = float(raw)
    except ValueError:
        return None
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _collect_supported_numbers(payload: Any) -> set[str]:
    supported: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
            return
        if isinstance(value, list):
            for child in value:
                visit(child)
            return
        if value is None:
            return
        text = str(value)
        for match in NUMERIC_TOKEN_PATTERN.findall(text):
            normalized = _normalize_numeric_token(match)
            if normalized:
                supported.add(normalized)

    visit(payload)
    now = datetime.now()
    for value in range(0, 11):
        supported.add(str(value))
    for value in [now.year, now.year - 1, now.year + 1]:
        supported.add(str(value))
    return supported


def _find_unsupported_numbers(draft_report: str, state: AgentState) -> list[str]:
    supported_numbers = _collect_supported_numbers(
        {
            "report_facts": state.get("report_facts", {}),
            "structured_facts": state.get("structured_facts", {}),
            "financial_facts": state.get("financial_facts", {}),
            "news_facts": state.get("news_facts", {}),
            "macro_facts": state.get("macro_facts", {}),
        }
    )
    unsupported: list[str] = []
    seen: set[str] = set()
    for match in NUMERIC_TOKEN_PATTERN.findall(draft_report or ""):
        normalized = _normalize_numeric_token(match)
        if not normalized or normalized in supported_numbers or normalized in seen:
            continue
        seen.add(normalized)
        unsupported.append(match)
    return unsupported


def financial_agent(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    category = state.get("category", "")
    logger.info("graph_node: financial_agent start (ticker=%s)", ticker)

    if category in ["INDEX", "BOND_US", "BOND_KR", "COMMODITY", "CRYPTO"]:
        logger.info("graph_node: financial_agent early-exit (ticker=%s, category=%s)", ticker, category)
        return {
            "financial_context": (
                "해당 자산(지수/채권/원자재/암호화폐)은 단일 기업 재무제표가 존재하지 않는 거시/대체 자산이므로 "
                "재무 분석을 생략합니다."
            ),
            "financial_facts": {
                "provider": "internal",
                "status": "not_applicable",
                "items": [],
                "limitations": ["이 자산군은 단일 기업 재무제표 분석 대상이 아닙니다."],
            },
        }

    fmp_facts: dict[str, Any] = {}
    if category == "STOCK_US":
        fmp_facts = _run_async(fetch_fmp_financials_structured(ticker))

    instructions = (
        "당신은 기업 재무 전문 조사원입니다. FMP 데이터와 검색 도구를 사용해 "
        "재무 지표, 밸류에이션, 실적 관련 팩트 원문을 최대한 상세히 수집하세요."
    )
    query = (
        f"ticker={ticker}\n"
        f"category={category}\n"
        f"price_data={state.get('price_data')}\n"
        f"[FMP Structured Facts]\n{fmp_facts}\n"
        f"[FMP Context]\n{format_provider_facts(fmp_facts) if fmp_facts else ''}\n"
        "최신 실적발표/가이던스/밸류에이션 근거 원문을 수집해라."
    )
    context = _run_research_agent("financial_agent", instructions, query)
    logger.info("graph_node: financial_agent done (ticker=%s)", ticker)
    return {"financial_context": context, "financial_facts": fmp_facts}


def news_agent(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    category = state.get("category", "")
    logger.info("graph_node: news_agent start (ticker=%s)", ticker)

    finnhub_facts: dict[str, Any] = {}
    if category == "STOCK_US":
        finnhub_facts = _run_async(fetch_finnhub_news_structured(ticker))

    instructions = (
        "당신은 뉴스 센티먼트 전문 조사원입니다. 최근 1주일 뉴스에서 호재/악재를 분리하고, "
        "시장 반응과 경영진 발언을 포함한 원문 팩트를 수집하세요."
    )
    query = (
        f"ticker={ticker}\n"
        f"category={category}\n"
        f"news_data={state.get('news_data')}\n"
        f"latest_context={state.get('latest_context')}\n"
        f"[Finnhub Structured Facts]\n{finnhub_facts}\n"
        f"[Finnhub Context]\n{format_provider_facts(finnhub_facts) if finnhub_facts else ''}\n"
        "최신 뉴스/공시/실적발표 일정의 헤드라인, 핵심내용, 시장 영향 근거를 수집해라. "
        "latest_context의 fetched_at과 source_status를 기준으로 데이터 신선도를 함께 판단해라."
    )
    context = _run_research_agent("news_agent", instructions, query)
    logger.info("graph_node: news_agent done (ticker=%s)", ticker)
    return {"news_context": context, "news_facts": finnhub_facts}


def macro_agent(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    category = state.get("category", "")
    logger.info("graph_node: macro_agent start (ticker=%s)", ticker)

    crypto_facts: dict[str, Any] = {}
    if category == "CRYPTO":
        crypto_facts = _run_async(fetch_coingecko_data_structured(ticker))

    instructions = (
        "당신은 거시/유동성 전문 조사원입니다. 환율, 금리, 인플레이션, 유동성, 달러 인덱스, "
        "리스크온/오프 지표를 검색 도구로 수집하고 자산 가격에 영향을 주는 팩트를 정리하세요. "
        "분석 대상이 채권/원자재라면 기업 실적 대신 기준금리/CPI/달러 인덱스와의 상관관계를 집중 분석하세요."
    )
    query = (
        f"ticker={ticker}\n"
        f"category={category}\n"
        f"[CoinGecko Structured Facts]\n{crypto_facts}\n"
        f"[CoinGecko Context]\n{format_provider_facts(crypto_facts) if crypto_facts else ''}\n"
        "거시경제/금리/환율/유동성 관련 최신 팩트를 수집해라."
    )
    context = _run_research_agent("macro_agent", instructions, query)
    logger.info("graph_node: macro_agent done (ticker=%s)", ticker)
    return {"macro_context": context, "macro_facts": crypto_facts}


def synthesizer_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: synthesizer_node start (ticker=%s)", ticker)
    llm = get_llm().with_structured_output(StructuredFacts)
    prompt = ChatPromptTemplate.from_template(
        "당신은 데이터 취합/정제 책임자다.\n"
        "report_facts는 가격, 뉴스, 이벤트, 소스 상태를 담은 정규화 입력이다.\n"
        "financial_facts, news_facts, macro_facts는 provider 응답에서 정규화한 추가 팩트다.\n"
        "report_facts, provider facts, financial_context, news_context, macro_context를 모두 읽고 모순을 해결해 "
        "단일 structured_facts로 병합하라.\n"
        "자료에 없는 숫자를 만들지 말고, 근거 기반으로만 작성하라. 모든 주요 숫자는 가능한 한 "
        "value, as_of, source, confidence 맥락을 보존하라.\n"
        "빈 데이터는 추측으로 채우지 말고 data_limitations에 명시하라.\n"
        "financial_context가 '재무 분석을 생략' 메시지라면 재무 수치를 억지로 만들지 말고 "
        "macro_context와 news_context에 100% 비중을 두어 정제하라.\n\n"
        "report_facts:\n{report_facts}\n\n"
        "financial_facts:\n{financial_facts}\n\n"
        "news_facts:\n{news_facts}\n\n"
        "macro_facts:\n{macro_facts}\n\n"
        "financial_context:\n{financial_context}\n\n"
        "news_context:\n{news_context}\n\n"
        "macro_context:\n{macro_context}\n"
    )
    chain = prompt | llm
    facts: StructuredFacts = chain.invoke(
        {
            "report_facts": state.get("report_facts", {}),
            "financial_facts": state.get("financial_facts", {}),
            "news_facts": state.get("news_facts", {}),
            "macro_facts": state.get("macro_facts", {}),
            "financial_context": state.get("financial_context", ""),
            "news_context": state.get("news_context", ""),
            "macro_context": state.get("macro_context", ""),
        }
    )
    logger.info("graph_node: synthesizer_node done (ticker=%s)", ticker)
    return {"structured_facts": facts.model_dump()}


def writer_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: writer_node start (ticker=%s)", ticker)
    llm = get_llm()
    prompt = ChatPromptTemplate.from_template(
        "당신은 시간의 흐름을 추적하는 수석 애널리스트입니다.\n"
        "전달받은 previous_report(과거 리포트)가 존재한다면, 현재 structured_facts와 비교하여 "
        "'무엇이 달라졌는지(Delta)'를 서론 맨 앞에 강렬하게 작성하세요.\n"
        "예: '6시간 전과 비교하여 시장 센티먼트가 긍정적으로 전환되었습니다.'\n"
        "과거 리포트가 없다면 일반적인 분석 리포트를 작성하세요.\n\n"
        "structured_facts와 feedback만을 기반으로 투자 리포트를 작성하라.\n"
        "아래 고정 섹션을 Markdown으로 유지하라: 1) 핵심 요약, 2) 데이터 기준 시각과 한계, "
        "3) 가격과 시장 반응, 4) Bull 시나리오, 5) Bear 시나리오, 6) 핵심 촉매, "
        "7) 주요 리스크, 8) 자산군별 분석, 9) 균형 결론, 10) 투자 유의사항.\n"
        "본문 초반에 데이터 기준 시각, 확인된 최신 뉴스/발표, 데이터 한계를 명시하라.\n"
        "확인된 사실과 해석을 구분하고, 직접적인 매수/매도 권고는 피하라.\n"
        "넘겨받지 않은 숫자를 만들지 말라.\n"
        "{language_requirement}\n\n"
        "previous_report:\n{previous_report}\n\n"
        "structured_facts:\n{structured_facts}\n\n"
        "feedback:\n{feedback}\n"
    )
    chain = prompt | llm
    result = chain.invoke(
        {
            "previous_report": state.get("previous_report", ""),
            "structured_facts": state.get("structured_facts", {}),
            "feedback": state.get("feedback", ""),
            "language_requirement": LANGUAGE_REQUIREMENT,
        }
    )
    draft = result.content
    logger.info("graph_node: writer_node done (ticker=%s)", ticker)
    return {"draft_report": draft, "analysis_result": draft, "final_report": draft}


def fact_checker_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: fact_checker_node start (ticker=%s)", ticker)
    unsupported_numbers = _find_unsupported_numbers(state.get("draft_report", ""), state)
    if not unsupported_numbers:
        logger.info("graph_node: fact_checker_node pass (ticker=%s)", ticker)
        return {"fact_check_pass": True, "fact_check_feedback": ""}

    sample = ", ".join(unsupported_numbers[:10])
    feedback = (
        "Fact checker failed: final draft contains numeric claims not found in structured facts. "
        f"Unsupported numbers: {sample}. "
        "Rewrite using only numbers present in structured_facts/report_facts/provider facts, "
        "or remove the unsupported numeric claim."
    )
    existing_feedback = state.get("feedback", "")
    combined_feedback = f"{existing_feedback}\n{feedback}".strip()
    next_revision = state.get("revision_count", 0) + 1
    logger.info(
        "graph_node: fact_checker_node fail (ticker=%s, unsupported=%s, revision_count->%s)",
        ticker,
        sample,
        next_revision,
    )
    return {
        "fact_check_pass": False,
        "fact_check_feedback": feedback,
        "feedback": combined_feedback,
        "is_pass": False,
        "revision_count": next_revision,
        "retry_count": state.get("retry_count", 0) + 1,
    }


def evaluator_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: evaluator_node start (ticker=%s)", ticker)
    current_year = datetime.now().year
    llm = get_llm().with_structured_output(EvaluationResult)
    prompt = ChatPromptTemplate.from_template(
        "당신은 깐깐한 편집장이다.\n"
        f"1) {current_year}년 최신성, 2) 팩트 무결성, 3) 한국어 품질, "
        "4) 데이터 한계 표기, 5) 지원되지 않은 숫자/주장 존재 여부를 평가하라.\n"
        "하나라도 미흡하면 FAIL과 구체 피드백, 완벽하면 PASS를 반환하라.\n\n"
        "draft_report:\n{draft_report}\n\n"
        "structured_facts:\n{structured_facts}\n"
    )
    chain = prompt | llm
    result: EvaluationResult = chain.invoke(
        {
            "draft_report": state.get("draft_report", ""),
            "structured_facts": state.get("structured_facts", {}),
        }
    )
    logger.info(
        "graph_node: evaluator_node done (ticker=%s, is_pass=%s, revision_count->%s)",
        ticker,
        result.is_pass,
        state.get("revision_count", 0) + 1,
    )
    return {
        "is_pass": result.is_pass,
        "feedback": result.feedback,
        "revision_count": state.get("revision_count", 0) + 1,
        "retry_count": state.get("retry_count", 0) + 1,
    }

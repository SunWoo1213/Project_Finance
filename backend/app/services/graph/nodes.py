from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from ..external_api_service import fetch_coingecko_data, fetch_finnhub_news, fetch_fmp_financials
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
    key_numbers: list[str] = Field(default_factory=list)
    market_sentiment_news: list[str] = Field(default_factory=list)
    bull_factors: list[str] = Field(default_factory=list)
    bear_factors: list[str] = Field(default_factory=list)
    summary: str = ""


class EvaluationResult(BaseModel):
    is_pass: bool = Field(description="리포트가 배포 가능한 품질이면 true")
    feedback: str = Field(description="개선 피드백")


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


def financial_agent(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    category = state.get("category", "")
    logger.info("graph_node: financial_agent start (ticker=%s)", ticker)

    if category in ["US_BOND", "KR_BOND", "COMMODITY", "CRYPTO"]:
        logger.info("graph_node: financial_agent early-exit (ticker=%s, category=%s)", ticker, category)
        return {
            "financial_context": (
                "해당 자산(채권/원자재/암호화폐)은 기업 재무제표가 존재하지 않는 거시/대체 자산이므로 "
                "재무 분석을 생략합니다."
            )
        }

    fmp_data = ""
    if category in ["US_STOCK", "KR_STOCK", "INDEX"]:
        fmp_data = _run_async(fetch_fmp_financials(ticker))

    instructions = (
        "당신은 기업 재무 전문 조사원입니다. FMP 데이터와 검색 도구를 사용해 "
        "재무 지표, 밸류에이션, 실적 관련 팩트 원문을 최대한 상세히 수집하세요."
    )
    query = (
        f"ticker={ticker}\n"
        f"category={category}\n"
        f"price_data={state.get('price_data')}\n"
        f"[FMP Context]\n{fmp_data}\n"
        "최신 실적발표/가이던스/밸류에이션 근거 원문을 수집해라."
    )
    context = _run_research_agent("financial_agent", instructions, query)
    logger.info("graph_node: financial_agent done (ticker=%s)", ticker)
    return {"financial_context": context}


def news_agent(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    category = state.get("category", "")
    logger.info("graph_node: news_agent start (ticker=%s)", ticker)

    finnhub_data = ""
    if category in ["US_STOCK", "KR_STOCK", "INDEX"]:
        finnhub_data = _run_async(fetch_finnhub_news(ticker))

    instructions = (
        "당신은 뉴스 센티먼트 전문 조사원입니다. 최근 1주일 뉴스에서 호재/악재를 분리하고, "
        "시장 반응과 경영진 발언을 포함한 원문 팩트를 수집하세요."
    )
    query = (
        f"ticker={ticker}\n"
        f"category={category}\n"
        f"news_data={state.get('news_data')}\n"
        f"[Finnhub Context]\n{finnhub_data}\n"
        "최신 뉴스의 헤드라인/핵심내용/시장 영향 근거를 수집해라."
    )
    context = _run_research_agent("news_agent", instructions, query)
    logger.info("graph_node: news_agent done (ticker=%s)", ticker)
    return {"news_context": context}


def macro_agent(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    category = state.get("category", "")
    logger.info("graph_node: macro_agent start (ticker=%s)", ticker)

    crypto_data = ""
    if category == "CRYPTO":
        crypto_data = _run_async(fetch_coingecko_data(ticker))

    instructions = (
        "당신은 거시/유동성 전문 조사원입니다. 환율, 금리, 인플레이션, 유동성, 달러 인덱스, "
        "리스크온/오프 지표를 검색 도구로 수집하고 자산 가격에 영향을 주는 팩트를 정리하세요. "
        "분석 대상이 채권/원자재라면 기업 실적 대신 기준금리/CPI/달러 인덱스와의 상관관계를 집중 분석하세요."
    )
    query = (
        f"ticker={ticker}\n"
        f"category={category}\n"
        f"[CoinGecko Context]\n{crypto_data}\n"
        "거시경제/금리/환율/유동성 관련 최신 팩트를 수집해라."
    )
    context = _run_research_agent("macro_agent", instructions, query)
    logger.info("graph_node: macro_agent done (ticker=%s)", ticker)
    return {"macro_context": context}


def synthesizer_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: synthesizer_node start (ticker=%s)", ticker)
    llm = get_llm().with_structured_output(StructuredFacts)
    prompt = ChatPromptTemplate.from_template(
        "당신은 데이터 취합/정제 책임자다.\n"
        "financial_context, news_context, macro_context를 모두 읽고 모순을 해결해 단일 structured_facts로 병합하라.\n"
        "자료에 없는 숫자를 만들지 말고, 근거 기반으로만 작성하라.\n"
        "financial_context가 '재무 분석을 생략' 메시지라면 재무 수치를 억지로 만들지 말고 "
        "macro_context와 news_context에 100% 비중을 두어 정제하라.\n\n"
        "financial_context:\n{financial_context}\n\n"
        "news_context:\n{news_context}\n\n"
        "macro_context:\n{macro_context}\n"
    )
    chain = prompt | llm
    facts: StructuredFacts = chain.invoke(
        {
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
        "서론, 본론(상승/하락 요인), 결론(투자 요약) 구조를 갖춘 Markdown으로 작성하라.\n"
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


def evaluator_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: evaluator_node start (ticker=%s)", ticker)
    current_year = datetime.now().year
    llm = get_llm().with_structured_output(EvaluationResult)
    prompt = ChatPromptTemplate.from_template(
        "당신은 깐깐한 편집장이다.\n"
        f"1) {current_year}년 최신성, 2) 팩트 무결성, 3) 한국어 품질을 평가하라.\n"
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

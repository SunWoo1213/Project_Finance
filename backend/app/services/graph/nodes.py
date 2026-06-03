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
    analysis_framework: dict[str, Any] = Field(default_factory=dict)
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
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?。！？])\s+|\n+")
FRAMEWORK_EVIDENCE_TERMS = [
    "데이터",
    "뉴스",
    "가격",
    "거래량",
    "수익률",
    "금리",
    "환율",
    "한계",
    "부족",
    "확인",
    "기준",
    "변동",
    "리스크",
    "공급",
    "수요",
    "정책",
    "실적",
    "시가총액",
]
QUALITATIVE_CLAIM_RULES = [
    {
        "label": "규제/ETF 이벤트",
        "triggers": ["규제 완화", "규제 승인", "규제 뉴스", "ETF 승인", "ETF 자금", "ETF 유입"],
        "evidence": ["규제", "ETF", "승인", "유입", "regulation", "regulatory"],
    },
    {
        "label": "기관 수급",
        "triggers": ["기관 수급", "기관 매수", "기관 자금", "수급이 강화", "자금 유입"],
        "evidence": ["기관", "수급", "자금", "유입", "flow", "institution"],
    },
    {
        "label": "실적/가이던스 개선",
        "triggers": ["실적 개선", "마진 개선", "가이던스 상향", "실적 호조", "수익성 개선"],
        "evidence": ["실적", "마진", "가이던스", "매출", "영업이익", "earnings", "guidance"],
    },
    {
        "label": "중앙은행 정책 전환",
        "triggers": ["정책이 완화", "완화적으로 전환", "금리 인하 전환", "중앙은행 정책", "연준 정책"],
        "evidence": ["정책", "금리", "연준", "한국은행", "중앙은행", "FOMC", "CPI", "inflation"],
    },
    {
        "label": "공급/재고 압박",
        "triggers": ["재고 부족", "공급 부족", "공급망 압박", "재고 감소"],
        "evidence": ["재고", "공급", "공급망", "inventory", "supply"],
    },
    {
        "label": "온체인/거래소 흐름",
        "triggers": ["온체인", "거래소 유출", "거래소 유입"],
        "evidence": ["온체인", "거래소", "onchain", "exchange"],
    },
]

REQUIRED_REPORT_SECTIONS = [
    ("핵심 요약", ["핵심요약"]),
    ("데이터 기준 시각과 한계", ["데이터기준시각과한계", "데이터기준시각", "데이터한계"]),
    ("가격과 시장 반응", ["가격과시장반응", "가격및시장반응", "시장반응과가격"]),
    ("Bull 시나리오", ["bull시나리오", "상승시나리오"]),
    ("Bear 시나리오", ["bear시나리오", "하락시나리오"]),
    ("핵심 촉매", ["핵심촉매", "주요촉매"]),
    ("주요 리스크", ["주요리스크", "핵심리스크"]),
    ("자산군별 분석", ["자산군별분석"]),
    ("균형 결론", ["균형결론", "종합결론"]),
    ("투자 유의사항", ["투자유의사항", "투자주의사항", "면책사항"]),
]


def _llm_with_flexible_structured_output(schema: type[BaseModel]):
    return get_llm().with_structured_output(schema, method="function_calling")


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


def _describe_supported_numbers(state: AgentState, limit: int = 40) -> list[str]:
    """fact_checker가 허용하는 동일 fact 소스에서 원문 숫자 토큰을 수집한다.

    `_find_unsupported_numbers`와 같은 payload를 순회하되, 정규화 이전의 원문
    토큰(예: ``200``, ``1.25%``)을 중복 제거하고 상한 개수만큼만 모은다. writer
    프롬프트에 화이트리스트로 주입해 첫 초안부터 미지원 숫자가 줄게 한다.
    """
    payload = {
        "report_facts": state.get("report_facts", {}),
        "structured_facts": state.get("structured_facts", {}),
        "financial_facts": state.get("financial_facts", {}),
        "news_facts": state.get("news_facts", {}),
        "macro_facts": state.get("macro_facts", {}),
    }
    tokens: list[str] = []
    seen: set[str] = set()

    def visit(value: Any) -> None:
        if len(tokens) >= limit:
            return
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
            if len(tokens) >= limit:
                return
            normalized = _normalize_numeric_token(match)
            if not normalized:
                continue
            key = match.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            tokens.append(key)

    visit(payload)
    return tokens


def _normalize_section_text(text: str) -> str:
    return re.sub(r"[\s#*`_\-:().\[\]0-9]+", "", text or "").casefold()


def _extract_markdown_heading_labels(draft_report: str) -> list[str]:
    headings: list[str] = []
    for line in (draft_report or "").splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            headings.append(match.group(1))
    return headings


def _extract_markdown_sections(draft_report: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_heading = ""
    for line in (draft_report or "").splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            current_heading = _normalize_section_text(match.group(1))
            sections.setdefault(current_heading, [])
            continue
        if current_heading:
            sections[current_heading].append(line)
    return {heading: "\n".join(lines).strip() for heading, lines in sections.items()}


def _find_section_block(draft_report: str, label: str, aliases: list[str] | None = None) -> str:
    sections = _extract_markdown_sections(draft_report)
    normalized_aliases = [_normalize_section_text(item) for item in [label, *(aliases or [])]]
    for alias in normalized_aliases:
        if alias in sections:
            return sections[alias]
    return ""


def _missing_report_sections(draft_report: str) -> list[str]:
    normalized_headings = [_normalize_section_text(heading) for heading in _extract_markdown_heading_labels(draft_report)]
    missing: list[str] = []
    for label, aliases in REQUIRED_REPORT_SECTIONS:
        normalized_aliases = [_normalize_section_text(alias) for alias in [label, *aliases]]
        if not any(alias == heading for alias in normalized_aliases for heading in normalized_headings):
            missing.append(label)
    return missing


def _topic_discussion_block(section_block: str, topic: str, all_topics: list[str]) -> str:
    topic_norm = _normalize_section_text(topic)
    other_topic_norms = [_normalize_section_text(item) for item in all_topics if item != topic]
    lines = section_block.splitlines()
    collected: list[str] = []
    collecting = False
    for line in lines:
        normalized_line = _normalize_section_text(line)
        if topic_norm and topic_norm in normalized_line:
            collecting = True
            collected.append(line)
            continue
        if collecting and any(other and other in normalized_line for other in other_topic_norms):
            break
        if collecting:
            collected.append(line)
    return "\n".join(collected).strip()


def _has_substantive_topic_discussion(text: str, topic: str) -> bool:
    if not text:
        return False
    normalized_text = _normalize_section_text(text)
    normalized_topic = _normalize_section_text(topic)
    residual = normalized_text.replace(normalized_topic, "")
    if len(residual) < 12:
        return False
    if NUMERIC_TOKEN_PATTERN.search(text):
        return True
    return any(term in text for term in FRAMEWORK_EVIDENCE_TERMS)


def _missing_framework_sections(draft_report: str, state: AgentState) -> list[str]:
    analysis_framework = (state.get("report_facts", {}) or {}).get("analysis_framework", {}) or {}
    required_sections = analysis_framework.get("required_sections") or []
    asset_framework_block = _find_section_block(draft_report, "자산군별 분석", ["자산군별분석"])
    missing: list[str] = []
    for section in required_sections:
        label = str(section).strip()
        if not label:
            continue
        topic_block = _topic_discussion_block(asset_framework_block, label, [str(item) for item in required_sections])
        if _normalize_section_text(label) not in _normalize_section_text(asset_framework_block):
            missing.append(label)
            continue
        if not _has_substantive_topic_discussion(topic_block, label):
            missing.append(label)
    return missing


def _collect_evidence_text(state: AgentState) -> str:
    report_facts = state.get("report_facts", {}) or {}
    structured_facts = state.get("structured_facts", {}) or {}
    payload = {
        "report_price": report_facts.get("price", {}),
        "report_market": report_facts.get("market", {}),
        "report_news": report_facts.get("news", []),
        "report_events": report_facts.get("events", []),
        "structured_price": structured_facts.get("price", {}),
        "structured_valuation": structured_facts.get("valuation", []),
        "structured_financials": structured_facts.get("financials", []),
        "structured_news": structured_facts.get("news", []),
        "structured_macro": structured_facts.get("macro", []),
        "structured_events": structured_facts.get("events", []),
        "structured_risks": structured_facts.get("risks", []),
        "structured_key_numbers": structured_facts.get("key_numbers", []),
        "market_sentiment_news": structured_facts.get("market_sentiment_news", []),
        "financial_facts": state.get("financial_facts", {}),
        "news_facts": state.get("news_facts", {}),
        "macro_facts": state.get("macro_facts", {}),
        "bull_thesis": state.get("bull_thesis", {}),
        "bear_thesis": state.get("bear_thesis", {}),
        "risk_review": state.get("risk_review", {}),
    }
    chunks: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
            return
        if isinstance(value, list):
            for child in value:
                visit(child)
            return
        if value is not None:
            chunks.append(str(value))

    visit(payload)
    return "\n".join(chunks)


def _find_unsupported_qualitative_claims(draft_report: str, state: AgentState) -> list[str]:
    evidence_text = _collect_evidence_text(state).casefold()
    unsupported: list[str] = []
    sentences = [item.strip() for item in SENTENCE_SPLIT_PATTERN.split(draft_report or "") if item.strip()]
    for sentence in sentences:
        normalized_sentence = sentence.casefold()
        for rule in QUALITATIVE_CLAIM_RULES:
            if not any(trigger.casefold() in normalized_sentence for trigger in rule["triggers"]):
                continue
            if any(term.casefold() in evidence_text for term in rule["evidence"]):
                continue
            unsupported.append(f"{rule['label']}: {sentence[:120]}")
            break
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
    llm = _llm_with_flexible_structured_output(StructuredFacts)
    prompt = ChatPromptTemplate.from_template(
        "당신은 데이터 취합/정제 책임자다.\n"
        "report_facts는 가격, 뉴스, 이벤트, 소스 상태를 담은 정규화 입력이다.\n"
        "report_facts.analysis_framework는 자산군별 분석 기준이다. structured_facts.analysis_framework에 보존하라.\n"
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


def _list_from_facts(value: Any) -> list[str]:
    if not value:
        return []
    if not isinstance(value, list):
        value = [value]

    items: list[str] = []
    for item in value:
        if isinstance(item, dict):
            for key in ("title", "summary", "label", "value"):
                if item.get(key):
                    items.append(str(item[key]))
                    break
            else:
                compact = ", ".join(f"{key}: {val}" for key, val in item.items() if val)
                if compact:
                    items.append(compact)
        else:
            text = str(item).strip()
            if text:
                items.append(text)
    return items


def _role_evidence(structured_facts: dict[str, Any], keys: list[str], limit: int = 5) -> list[str]:
    evidence: list[str] = []
    for key in keys:
        for item in _list_from_facts(structured_facts.get(key)):
            if item not in evidence:
                evidence.append(item)
            if len(evidence) >= limit:
                return evidence
    return evidence


def _fallback_thesis(message: str, structured_facts: dict[str, Any]) -> list[str]:
    limitations = _list_from_facts(structured_facts.get("data_limitations"))
    if limitations:
        return [message, *limitations[:2]]
    return [message]


def bull_agent_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: bull_agent_node start (ticker=%s)", ticker)
    structured_facts = state.get("structured_facts", {}) or {}
    thesis = _list_from_facts(structured_facts.get("bull_factors"))
    if not thesis:
        thesis = _role_evidence(structured_facts, ["market_sentiment_news", "news", "events"], limit=3)
    if not thesis:
        thesis = _fallback_thesis("명확한 상승 논거가 구조화 팩트에서 확인되지 않았습니다.", structured_facts)

    return {
        "bull_thesis": {
            "role": "bull_agent",
            "stance": "positive_scenario",
            "thesis": thesis[:5],
            "evidence": _role_evidence(
                structured_facts,
                ["price", "valuation", "financials", "news", "macro", "events"],
            ),
            "limitations": _list_from_facts(structured_facts.get("data_limitations"))[:5],
        }
    }


def bear_agent_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: bear_agent_node start (ticker=%s)", ticker)
    structured_facts = state.get("structured_facts", {}) or {}
    thesis = _list_from_facts(structured_facts.get("bear_factors"))
    if not thesis:
        thesis = _role_evidence(structured_facts, ["risks", "data_limitations"], limit=3)
    if not thesis:
        thesis = _fallback_thesis("명확한 하락 논거가 구조화 팩트에서 확인되지 않았습니다.", structured_facts)

    return {
        "bear_thesis": {
            "role": "bear_agent",
            "stance": "negative_scenario",
            "thesis": thesis[:5],
            "evidence": _role_evidence(
                structured_facts,
                ["risks", "data_limitations", "valuation", "financials", "news", "macro"],
            ),
            "limitations": _list_from_facts(structured_facts.get("data_limitations"))[:5],
        }
    }


def risk_officer_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: risk_officer_node start (ticker=%s)", ticker)
    structured_facts = state.get("structured_facts", {}) or {}
    report_facts = state.get("report_facts", {}) or {}
    missing_required = _list_from_facts(report_facts.get("missing_required_facts"))
    risk_factors = _list_from_facts(structured_facts.get("risk_factors") or structured_facts.get("risks"))
    limitations = _list_from_facts(structured_facts.get("data_limitations"))

    findings = [*risk_factors[:5], *limitations[:5]]
    if missing_required:
        findings.append(f"누락된 필수 팩트: {', '.join(missing_required)}")
    if not findings:
        findings = ["구조화 팩트에서 별도 리스크가 충분히 분리되지 않았습니다."]

    return {
        "risk_review": {
            "role": "risk_officer",
            "stance": "risk_and_uncertainty",
            "findings": findings[:8],
            "missing_required_facts": missing_required,
            "source_status": report_facts.get("source_status", {}),
        }
    }


def _source_table_from_state(state: AgentState) -> list[dict[str, Any]]:
    report_facts = state.get("report_facts", {}) or {}
    structured_facts = state.get("structured_facts", {}) or {}
    source_table: list[dict[str, Any]] = []

    price = report_facts.get("price") or {}
    if price.get("value") not in (None, "", 0):
        source_table.append(
            {
                "id": "PRICE",
                "label": "Price snapshot",
                "source": price.get("source", "market_cache"),
                "as_of": price.get("as_of", ""),
                "confidence": price.get("confidence", "unknown"),
            }
        )

    for index, item in enumerate(report_facts.get("news") or [], start=1):
        source_table.append(
            {
                "id": f"NEWS_{index}",
                "label": item.get("title") or f"News item {index}",
                "source": item.get("source", "unknown"),
                "as_of": item.get("as_of", ""),
                "url": item.get("url", ""),
                "confidence": item.get("confidence", "unknown"),
            }
        )

    for index, item in enumerate(report_facts.get("events") or [], start=1):
        source_table.append(
            {
                "id": f"EVENT_{index}",
                "label": item.get("title") or f"Event {index}",
                "source": item.get("source", "unknown"),
                "as_of": item.get("as_of", ""),
                "confidence": item.get("confidence", "unknown"),
            }
        )

    for provider_key, evidence_id in (
        ("financial_facts", "PROVIDER_FINANCIAL"),
        ("news_facts", "PROVIDER_NEWS"),
        ("macro_facts", "PROVIDER_MACRO"),
    ):
        facts = state.get(provider_key, {}) or {}
        if facts:
            source_table.append(
                {
                    "id": evidence_id,
                    "label": provider_key.replace("_", " ").title(),
                    "source": facts.get("provider", provider_key),
                    "status": facts.get("status", "available"),
                }
            )

    if report_facts.get("fact_matrix"):
        source_table.append(
            {
                "id": "FACT_MATRIX",
                "label": "Fact matrix",
                "source": "deterministic_readiness_gate",
                "status": (report_facts.get("readiness") or {}).get("status", "unknown"),
            }
        )

    if structured_facts:
        source_table.append(
            {
                "id": "STRUCTURED_FACTS",
                "label": "Structured facts",
                "source": "synthesizer_node",
                "status": "available",
            }
        )

    return source_table


def _available_evidence_ids(source_table: list[dict[str, Any]]) -> list[str]:
    return [str(item["id"]) for item in source_table if item.get("id")]


def _packet_section(
    title: str,
    items: list[str],
    evidence_ids: list[str],
    limitation_reason: str = "",
) -> dict[str, Any]:
    return {
        "title": title,
        "items": items[:8],
        "evidence_ids": evidence_ids[:6] if items else [],
        "limitation_reason": "" if items else limitation_reason,
    }


def research_packet_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: research_packet_node start (ticker=%s)", ticker)
    structured_facts = state.get("structured_facts", {}) or {}
    report_facts = state.get("report_facts", {}) or {}
    bull_thesis = state.get("bull_thesis", {}) or {}
    bear_thesis = state.get("bear_thesis", {}) or {}
    risk_review = state.get("risk_review", {}) or {}
    source_table = _source_table_from_state(state)
    evidence_ids = _available_evidence_ids(source_table)
    default_evidence = evidence_ids or ["STRUCTURED_FACTS"]

    base_items = _list_from_facts(structured_facts.get("summary"))
    if not base_items:
        base_items = _list_from_facts(structured_facts.get("key_numbers"))
    if not base_items:
        base_items = _list_from_facts(structured_facts.get("market_sentiment_news"))

    catalysts = _list_from_facts(structured_facts.get("events"))[:5]
    if not catalysts:
        catalysts = _list_from_facts(structured_facts.get("news"))[:5]

    watchlist = _list_from_facts(report_facts.get("missing_required_facts"))
    watchlist.extend(_list_from_facts(structured_facts.get("risk_factors"))[:5])
    watchlist = list(dict.fromkeys(watchlist))[:8]

    packet = {
        "base_case": _packet_section(
            "Base case",
            base_items,
            default_evidence,
            "No synthesized base-case facts were available.",
        ),
        "bull_case": _packet_section(
            "Bull case",
            _list_from_facts(bull_thesis.get("thesis")),
            _list_from_facts(bull_thesis.get("evidence")) and default_evidence,
            "Insufficient evidence for a supported bull case.",
        ),
        "bear_case": _packet_section(
            "Bear case",
            _list_from_facts(bear_thesis.get("thesis")),
            _list_from_facts(bear_thesis.get("evidence")) and default_evidence,
            "Insufficient evidence for a supported bear case.",
        ),
        "risk_review": _packet_section(
            "Risk review",
            _list_from_facts(risk_review.get("findings")),
            ["FACT_MATRIX", *default_evidence],
            "No structured risk review was available.",
        ),
        "catalysts": catalysts,
        "watchlist": watchlist,
        "source_table": source_table,
        "data_limitations": _list_from_facts(structured_facts.get("data_limitations") or report_facts.get("data_limitations")),
        "prior_report_delta": _packet_section(
            "Prior report delta",
            [],
            [],
            "Prior-report comparison is not yet deterministic in this implementation slice.",
        ),
    }
    logger.info("graph_node: research_packet_node done (ticker=%s)", ticker)
    return {"research_packet": packet}


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
        "structured_facts, analysis_framework, bull_thesis, bear_thesis, risk_review, feedback만을 기반으로 투자 리포트를 작성하라.\n"
        "아래 고정 섹션을 Markdown으로 유지하라: 1) 핵심 요약, 2) 데이터 기준 시각과 한계, "
        "3) 가격과 시장 반응, 4) Bull 시나리오, 5) Bear 시나리오, 6) 핵심 촉매, "
        "7) 주요 리스크, 8) 자산군별 분석, 9) 균형 결론, 10) 투자 유의사항.\n"
        "8) 자산군별 분석 섹션은 analysis_framework.required_sections와 "
        "analysis_framework.interpretation_rules를 우선 기준으로 작성하라. "
        "각 required_sections 항목은 반드시 8) 자산군별 분석 섹션 안에 쓰고, "
        "라벨만 나열하지 말고 확인된 근거 또는 데이터 한계 문장을 함께 작성하라.\n"
        "본문 초반에 데이터 기준 시각, 확인된 최신 뉴스/발표, 데이터 한계를 명시하라.\n"
        "확인된 사실과 해석을 구분하고, 직접적인 매수/매도 권고는 피하라.\n"
        "규제, ETF, 기관 수급, 실적 개선, 중앙은행 정책 전환, 재고/공급, 온체인 흐름 같은 "
        "정성 클레임은 structured_facts나 provider facts에 근거가 있을 때만 사용하라.\n"
        "숫자 규율(엄수): 아래 allowed_numbers 목록에 있는 숫자, 0~10 사이 정수, "
        "연도(예: 2026)만 본문에 쓸 수 있다. 이 범위를 벗어난 숫자는 절대 만들지 말 것. "
        "추가 수치가 필요하면 숫자 대신 정성 서술로 바꾸거나 '데이터 한계'로 명시하라. "
        "allowed_numbers가 비어 있으면 가격/기준 숫자 외의 어떤 수치도 쓰지 말 것.\n"
        "allowed_numbers(원문 그대로 사용 가능한 숫자 토큰):\n{allowed_numbers}\n"
        "Research packet discipline: research_packet is the controlling packet. Do not invent analysis outside its entries, evidence IDs, source table, and data limitations.\n"
        "{language_requirement}\n\n"
        "previous_report:\n{previous_report}\n\n"
        "structured_facts:\n{structured_facts}\n\n"
        "research_packet:\n{research_packet}\n\n"
        "analysis_framework:\n{analysis_framework}\n\n"
        "bull_thesis:\n{bull_thesis}\n\n"
        "bear_thesis:\n{bear_thesis}\n\n"
        "risk_review:\n{risk_review}\n\n"
        "feedback:\n{feedback}\n"
    )
    allowed_tokens = _describe_supported_numbers(state)
    if allowed_tokens:
        allowed_numbers = ", ".join(allowed_tokens)
    else:
        allowed_numbers = "(확정된 숫자가 없습니다. 가격/기준 숫자 외의 수치를 쓰지 마세요.)"
    chain = prompt | llm
    result = chain.invoke(
        {
            "previous_report": state.get("previous_report", ""),
            "structured_facts": state.get("structured_facts", {}),
            "research_packet": state.get("research_packet", {}),
            "analysis_framework": (state.get("report_facts", {}) or {}).get("analysis_framework", {}),
            "bull_thesis": state.get("bull_thesis", {}),
            "bear_thesis": state.get("bear_thesis", {}),
            "risk_review": state.get("risk_review", {}),
            "feedback": state.get("feedback", ""),
            "allowed_numbers": allowed_numbers,
            "language_requirement": LANGUAGE_REQUIREMENT,
        }
    )
    draft = result.content
    logger.info("graph_node: writer_node done (ticker=%s)", ticker)
    return {"draft_report": draft, "analysis_result": draft, "final_report": draft}


def report_format_validator_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: report_format_validator_node start (ticker=%s)", ticker)
    draft_report = state.get("draft_report", "")
    missing_sections = _missing_report_sections(draft_report)
    missing_framework_sections = _missing_framework_sections(draft_report, state)
    if not missing_sections and not missing_framework_sections:
        logger.info("graph_node: report_format_validator_node pass (ticker=%s)", ticker)
        return {"format_check_pass": True, "format_check_feedback": ""}

    missing_parts = []
    if missing_sections:
        missing_parts.append(f"Missing fixed sections: {', '.join(missing_sections)}")
    if missing_framework_sections:
        missing_parts.append(f"Missing asset-framework topics: {', '.join(missing_framework_sections)}")
    feedback = (
        "Report format check failed: final draft does not satisfy the required template. "
        f"{'; '.join(missing_parts)}. "
        "Rewrite the report using all 10 fixed Markdown sections in order, and make the "
        "자산군별 분석 section explicitly cover every asset-framework topic."
    )
    existing_feedback = state.get("feedback", "")
    combined_feedback = f"{existing_feedback}\n{feedback}".strip()
    next_revision = state.get("revision_count", 0) + 1
    logger.info(
        "graph_node: report_format_validator_node fail (ticker=%s, missing=%s, revision_count->%s)",
        ticker,
        "; ".join(missing_parts),
        next_revision,
    )
    return {
        "format_check_pass": False,
        "format_check_feedback": feedback,
        "feedback": combined_feedback,
        "is_pass": False,
        "revision_count": next_revision,
        "retry_count": state.get("retry_count", 0) + 1,
    }


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


def qualitative_claim_checker_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: qualitative_claim_checker_node start (ticker=%s)", ticker)
    unsupported_claims = _find_unsupported_qualitative_claims(state.get("draft_report", ""), state)
    if not unsupported_claims:
        logger.info("graph_node: qualitative_claim_checker_node pass (ticker=%s)", ticker)
        return {"qualitative_check_pass": True, "qualitative_check_feedback": ""}

    feedback = (
        "Qualitative claim check failed: the draft contains high-risk qualitative claims "
        "without matching structured evidence. Unsupported claims: "
        f"{'; '.join(unsupported_claims[:5])}. "
        "Rewrite by either citing the available source facts or downgrading the claim into a data limitation."
    )
    existing_feedback = state.get("feedback", "")
    combined_feedback = f"{existing_feedback}\n{feedback}".strip()
    next_revision = state.get("revision_count", 0) + 1
    logger.info(
        "graph_node: qualitative_claim_checker_node fail (ticker=%s, unsupported=%s, revision_count->%s)",
        ticker,
        "; ".join(unsupported_claims[:5]),
        next_revision,
    )
    return {
        "qualitative_check_pass": False,
        "qualitative_check_feedback": feedback,
        "feedback": combined_feedback,
        "is_pass": False,
        "revision_count": next_revision,
        "retry_count": state.get("retry_count", 0) + 1,
    }


def evaluator_node(state: AgentState) -> dict[str, Any]:
    ticker = state.get("ticker", "")
    logger.info("graph_node: evaluator_node start (ticker=%s)", ticker)
    current_year = datetime.now().year
    llm = _llm_with_flexible_structured_output(EvaluationResult)
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

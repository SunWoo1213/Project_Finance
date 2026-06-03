"""LLM-backed intent understanding for the chatbot assistant.

This module makes the chatbot less passive and better at understanding natural
language, while staying grounded and safe:

- It never generates AI reports. No report-generation tool exists here. The
  caller passes an already-fetched *stored* report summary only (AGENTS.md
  section 14: users/chatbot read stored scheduled reports only).
- It does not hallucinate market data. The caller gathers candidates, category,
  a cached market snippet, and the stored report summary deterministically and
  passes them as grounding. The LLM may only use the supplied grounding; if a
  fact is not present it must say it does not know.
- It is a thin layer: it decides intent, writes the answer, and selects which of
  the pre-built actions to surface. Action URLs are built by the caller, so the
  browser navigation contract (backend returns actions, never navigates) holds.

The whole path is gated by ``settings.ENABLE_LLM_CHATBOT``. Any failure returns
``None`` so the caller can fall back to the deterministic rule-based response.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field

from ..core.config import settings

logger = logging.getLogger(__name__)


ALLOWED_INTENTS = {
    "asset_detail_navigation",
    "market_snapshot_navigation",
    "category_navigation",
    "report_help",
    "community_help",
    "auth_help",
    "favorite_help",
    "market_summary",
    "current_page_help",
    "non_financial",
    "unknown",
}


SYSTEM_PROMPT = (
    "당신은 Project Finance 앱의 금융 도우미 챗봇입니다. 한국어로 친절하고 능동적으로 답합니다.\n"
    "범위: 금융 데이터, 시세, 뉴스, 투자 리포트, 그리고 이 앱의 기능 안내(자산 상세, 카테고리, "
    "커뮤니티, 즐겨찾기, 로그인)로 한정합니다. 범위를 벗어난 질문에는 intent를 'non_financial'로 두고 "
    "정중히 거절합니다.\n"
    "매우 중요한 규칙:\n"
    "1. 제공된 grounding 데이터(자산 후보, 카테고리, 시장 스냅샷, 저장 리포트 요약)에 있는 사실만 "
    "사용합니다. grounding에 없는 수치·전망·뉴스를 지어내지 마세요. 모르면 모른다고 답합니다.\n"
    "2. 당신은 AI 리포트를 생성하지 않습니다. 리포트 질문에는 grounding의 '저장 리포트 요약'만 전하고, "
    "요약이 없으면 아직 저장된 리포트가 없다고 안내합니다. 생성을 약속하지 마세요.\n"
    "3. 매수·매도를 단정하거나 권유하지 않습니다.\n"
    "4. 화면 이동은 사용자가 버튼을 눌러 진행합니다. 답변에 어울리는 액션을 actions 목록에서 골라 "
    "action_indices(0부터 시작하는 인덱스)로 반환하세요. 관련 없는 액션은 넣지 않습니다.\n"
    "5. answer는 2~4문장으로 핵심을 먼저 말하고, 데이터가 있으면 구체적으로 전합니다.\n"
    "intent는 다음 중 하나여야 합니다: "
    + ", ".join(sorted(ALLOWED_INTENTS))
    + "."
)


class LlmChatPlan(BaseModel):
    """Structured output the LLM must return."""

    answer: str = Field(..., description="사용자에게 보여줄 한국어 답변")
    intent: str = Field(..., description="분류된 intent")
    confidence: float = Field(0.7, ge=0.0, le=1.0)
    action_indices: list[int] = Field(
        default_factory=list,
        description="grounding.actions 중 노출할 항목의 0-기반 인덱스",
    )


def _get_structured_llm():
    # Imported lazily so importing this module never requires langchain at load
    # time (keeps the rule-based path import-safe when the dependency is absent).
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.CHATBOT_LLM_MODEL,
        temperature=0.3,
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.CHATBOT_LLM_TIMEOUT_SECONDS,
        max_retries=0,
    )
    return llm.with_structured_output(LlmChatPlan)


def _grounding_block(grounding: dict[str, Any]) -> str:
    lines: list[str] = []
    candidates = grounding.get("candidates") or []
    if candidates:
        names = ", ".join(f"{c['name']}({c['ticker']})" for c in candidates)
        lines.append(f"자산 후보: {names}")
    if grounding.get("category"):
        lines.append(f"카테고리 해석: {grounding['category']}")
    if grounding.get("current_ticker"):
        lines.append(f"현재 화면 자산: {grounding['current_ticker']}")
    lines.append(f"로그인 상태: {'예' if grounding.get('authenticated') else '아니오'}")
    if grounding.get("market_snippet"):
        lines.append(f"시장 스냅샷(캐시): {grounding['market_snippet']}")
    if grounding.get("report_summary"):
        lines.append(f"저장 리포트 요약: {grounding['report_summary']}")
    else:
        lines.append("저장 리포트 요약: 없음")
    actions = grounding.get("actions") or []
    if actions:
        action_lines = [
            f"  [{i}] {a.get('label')} — {a.get('reason', '')}".rstrip(" —")
            for i, a in enumerate(actions)
        ]
        lines.append("선택 가능한 actions:\n" + "\n".join(action_lines))
    else:
        lines.append("선택 가능한 actions: 없음")
    return "\n".join(lines)


def _history_messages(history: list[dict[str, str]]) -> list[tuple[str, str]]:
    trimmed = history[-(settings.CHATBOT_HISTORY_MAX_TURNS * 2) :]
    messages: list[tuple[str, str]] = []
    for turn in trimmed:
        role = "ai" if turn.get("role") == "assistant" else "human"
        content = (turn.get("content") or "").strip()
        if content:
            messages.append((role, content))
    return messages


async def compose_chat_answer(
    *,
    message: str,
    history: list[dict[str, str]],
    grounding: dict[str, Any],
) -> LlmChatPlan | None:
    """Run the LLM to produce an intent + grounded answer + chosen action indices.

    Returns ``None`` on any failure so the caller can fall back to rules.
    """

    if not settings.ENABLE_LLM_CHATBOT or not settings.OPENAI_API_KEY:
        return None

    try:
        structured_llm = _get_structured_llm()
        messages: list[tuple[str, str]] = [("system", SYSTEM_PROMPT)]
        messages.extend(_history_messages(history))
        messages.append(
            (
                "human",
                f"사용자 질문: {message}\n\n[grounding 데이터]\n{_grounding_block(grounding)}",
            )
        )
        plan = await asyncio.wait_for(
            structured_llm.ainvoke(messages),
            timeout=settings.CHATBOT_LLM_TIMEOUT_SECONDS + 5,
        )
    except Exception:  # noqa: BLE001 - any failure must fall back to rules
        logger.warning("LLM chatbot path failed; falling back to rules", exc_info=True)
        return None

    if not isinstance(plan, LlmChatPlan):
        return None
    if plan.intent not in ALLOWED_INTENTS:
        plan.intent = "unknown"
    # Defend against out-of-range indices from the model.
    action_count = len(grounding.get("actions") or [])
    plan.action_indices = [i for i in plan.action_indices if 0 <= i < action_count]
    if not (plan.answer or "").strip():
        return None
    return plan

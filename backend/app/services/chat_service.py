from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.cache import market_cache
from ..core.config import settings
from ..models import AIReport, Asset, User
from ..schemas import ChatContext, ChatMessageRequest, ChatResponse
from . import chat_grounding, chat_llm
from .chat_tools import (
    ambiguous_bond_candidates,
    action_for_asset,
    card_for_asset,
    category_action,
    detect_feature,
    display_name_for_ticker,
    find_asset_candidates,
    find_category,
    is_financial_query,
    login_action,
)
from .market_service import fetch_latest_asset_context


DISCLAIMER = "제공 정보는 투자 참고용이며 매수·매도 판단을 대신하지 않습니다."
NON_FINANCIAL_ANSWER = (
    "죄송하지만 저는 금융 데이터, 투자 리포트, 시장 정보, 그리고 Project Finance 앱 기능 안내를 돕는 챗봇입니다. "
    "금융 관련 질문만 해주세요."
)


async def handle_chat_message(
    payload: ChatMessageRequest,
    current_user: User | None,
    db: AsyncSession,
) -> ChatResponse:
    message = payload.message.strip()
    context = payload.context or ChatContext()
    authenticated = bool(current_user or context.authenticated)

    if settings.ENABLE_LLM_CHATBOT and settings.OPENAI_API_KEY:
        llm_response = await _try_llm_response(
            payload=payload,
            message=message,
            context=context,
            authenticated=authenticated,
            current_user=current_user,
            db=db,
        )
        if llm_response is not None:
            return llm_response
        # Any failure falls through to the deterministic rule-based path below.

    if not is_financial_query(message):
        return ChatResponse(
            answer=NON_FINANCIAL_ANSWER,
            intent="non_financial",
            confidence=0.93,
            actions=[],
            cards=[],
            disclaimer=None,
        )

    feature = detect_feature(message)
    candidates = find_asset_candidates(message)
    current_ticker = _context_ticker(payload.current_path, context)
    category = find_category(message)

    if feature == "auth":
        return _auth_help_response()

    if feature == "report":
        return await _report_help_response(
            candidates=candidates,
            current_ticker=current_ticker,
            authenticated=authenticated,
            current_user=current_user,
            db=db,
        )

    if feature == "community":
        return _community_help_response(candidates, current_ticker, authenticated)

    if feature == "favorite":
        return _favorite_help_response(candidates, current_ticker)

    if feature == "current_page":
        return _current_page_response(payload.current_path, current_ticker, authenticated)

    if feature == "market_summary":
        return await _market_summary_response(candidates, current_ticker)

    if category and (_looks_like_category_request(message) or not candidates):
        actions = [category_action(category)]
        cards = []
        if category["key"] == "bonds":
            bond_candidates = ambiguous_bond_candidates()
            actions.extend(action_for_asset(candidate, confidence=candidate.score) for candidate in bond_candidates)
            cards.extend(card_for_asset(candidate) for candidate in bond_candidates)
            answer = "채권 목록을 먼저 보거나 대표 금리 자산을 바로 열 수 있습니다."
            confidence = 0.72
            intent = "unknown" if _is_ambiguous(message) else "category_navigation"
        else:
            answer = f"{category['label']} 목록에서 관련 자산 흐름을 확인할 수 있습니다."
            confidence = 0.84
            intent = "category_navigation"
        return ChatResponse(
            answer=answer,
            intent=intent,
            confidence=confidence,
            actions=actions,
            cards=cards,
            disclaimer=DISCLAIMER,
        )

    if len(candidates) > 1 and _is_ambiguous(message):
        return ChatResponse(
            answer="어떤 대상을 보고 싶은지 골라주세요.",
            intent="unknown",
            confidence=0.48,
            actions=[action_for_asset(candidate, confidence=candidate.score) for candidate in candidates],
            cards=[card_for_asset(candidate) for candidate in candidates],
            disclaimer=DISCLAIMER,
        )

    if candidates:
        candidate = candidates[0]
        if candidate.route_type == "market":
            return ChatResponse(
                answer=f"{candidate.name}은 주요 지수·환율 스냅샷 화면에서 1일 흐름을 볼 수 있습니다.",
                intent="market_snapshot_navigation",
                confidence=candidate.score,
                actions=[action_for_asset(candidate, label_suffix="보기")],
                cards=[card_for_asset(candidate)],
                disclaimer=DISCLAIMER,
            )
        return ChatResponse(
            answer=f"{candidate.name} 상세 페이지에서 가격, 차트, 최신 뉴스, AI 리포트와 커뮤니티를 확인할 수 있습니다.",
            intent="asset_detail_navigation",
            confidence=candidate.score,
            actions=[action_for_asset(candidate, label_suffix="보기")],
            cards=[card_for_asset(candidate)],
            disclaimer=DISCLAIMER,
        )

    return ChatResponse(
        answer="어떤 자산이나 기능을 찾는지 조금 더 구체적으로 알려주세요. 예: 테슬라 리포트, 코인 목록, 나스닥 흐름",
        intent="unknown",
        confidence=0.36,
        actions=[
            category_action({"label": "미국 주식 TOP10", "route": "/category/us_top10"}, confidence=0.5),
            category_action({"label": "암호화폐", "route": "/category/cryptos"}, confidence=0.5),
            category_action({"label": "주요 지수·환율", "route": "/category/macro"}, confidence=0.5),
        ],
        disclaimer=DISCLAIMER,
    )


async def _try_llm_response(
    *,
    payload: ChatMessageRequest,
    message: str,
    context: ChatContext,
    authenticated: bool,
    current_user: User | None,
    db: AsyncSession,
) -> ChatResponse | None:
    """Attempt an LLM-grounded response. Returns None to fall back to rules.

    The LLM never generates reports: it only receives an already-fetched stored
    report summary and a cached market snippet as grounding. Actions/cards are
    built deterministically here so navigation URLs stay correct.
    """

    try:
        candidates = find_asset_candidates(message)
        category = find_category(message)
        current_ticker = _context_ticker(payload.current_path, context)
        primary_ticker = candidates[0].ticker if candidates else current_ticker

        actions: list[dict] = []
        cards: list[dict] = []
        for candidate in candidates:
            actions.append(action_for_asset(candidate, label_suffix="보기"))
            cards.append(card_for_asset(candidate))
        if category:
            actions.append(category_action(category))
        if current_ticker and not candidates:
            name = display_name_for_ticker(current_ticker)
            actions.append(
                {
                    "type": "navigate",
                    "label": f"{name} 상세 페이지 보기",
                    "url": f"/detail/{_quote_path(current_ticker)}",
                    "reason": "현재 화면의 자산 맥락을 유지합니다.",
                    "confidence": 0.78,
                    "requires_auth": False,
                }
            )
            cards.append({"type": "asset", "ticker": current_ticker, "name": name, "route": f"/detail/{_quote_path(current_ticker)}"})
        if not authenticated:
            actions.append(login_action())

        report_summary = None
        if authenticated and current_user is not None and primary_ticker:
            report = await _fetch_saved_report(primary_ticker, db)
            if report is not None:
                report_summary = _summarize_report(report)

        # Structured snapshots for every resolved ticker keep the grounded
        # number set accurate; the snippet stays for human-readable context.
        quote_tickers = [c.ticker for c in candidates] or ([current_ticker] if current_ticker else [])
        quotes = [q for q in (chat_grounding.asset_snapshot(t) for t in quote_tickers) if q]

        grounding = {
            "candidates": [{"name": c.name, "ticker": c.ticker} for c in candidates],
            "category": category["label"] if category else None,
            "current_ticker": current_ticker,
            "authenticated": authenticated,
            "market_snippet": chat_grounding.asset_snippet(primary_ticker),
            "quotes": quotes,
            "report_summary": report_summary,
            "actions": actions,
        }

        history = [turn.model_dump() for turn in (payload.history or [])]
        plan = await chat_llm.compose_chat_answer(
            message=message, history=history, grounding=grounding
        )
    except Exception:  # noqa: BLE001 - fall back to rules on any error
        return None

    if plan is None:
        return None

    answer = plan.answer
    confidence = plan.confidence
    # Numeric guard: never surface price/percent figures that are not backed by
    # the assembled grounding. We do not rewrite the sentence; we lower
    # confidence and add a short caveat so the user is not misled.
    if settings.CHATBOT_GROUNDING_GUARD:
        guard = chat_grounding.guard_answer(answer, grounding)
        if not guard.grounded:
            confidence = min(confidence, 0.5)
            answer = f"{answer} (일부 수치는 최신 캐시에서 확인되지 않아 참고용으로만 봐주세요.)"

    selected_actions = [actions[i] for i in plan.action_indices]
    disclaimer = None if plan.intent == "non_financial" else DISCLAIMER
    return ChatResponse(
        answer=answer,
        intent=plan.intent,
        confidence=confidence,
        actions=selected_actions,
        cards=cards if plan.intent != "non_financial" else [],
        requires_auth=not authenticated and plan.intent in {"report_help", "community_help", "auth_help"},
        disclaimer=disclaimer,
    )


def _auth_help_response() -> ChatResponse:
    return ChatResponse(
        answer="로그인은 Google 계정으로 진행합니다. 로그인하면 AI 리포트 조회와 댓글 작성, 좋아요, 신고 기능을 사용할 수 있습니다.",
        intent="auth_help",
        confidence=0.94,
        actions=[login_action("로그인 화면으로 이동합니다.")],
        disclaimer=DISCLAIMER,
    )


async def _report_help_response(
    candidates: list,
    current_ticker: str | None,
    authenticated: bool,
    current_user: User | None,
    db: AsyncSession,
) -> ChatResponse:
    candidate = candidates[0] if candidates else None
    ticker = candidate.ticker if candidate else current_ticker
    name = candidate.name if candidate else display_name_for_ticker(ticker or "")

    if not ticker:
        return ChatResponse(
            answer="어떤 자산의 AI 리포트를 보고 싶은지 알려주세요. 예: 테슬라 리포트, 삼성전자 보고서",
            intent="report_help",
            confidence=0.58,
            actions=[
                category_action({"label": "미국 주식 TOP10", "route": "/category/us_top10"}, confidence=0.54),
                category_action({"label": "한국 주식 TOP10", "route": "/category/kr_top10"}, confidence=0.54),
            ],
            requires_auth=not authenticated,
            disclaimer=DISCLAIMER,
        )

    detail_action = {
        "type": "navigate",
        "label": f"{name} 상세 페이지 보기",
        "url": f"/detail/{_quote_path(ticker)}",
        "reason": "AI 리포트 영역은 자산 상세 페이지에 있습니다.",
        "confidence": 0.87,
        "requires_auth": False,
    }

    if not authenticated or current_user is None:
        return ChatResponse(
            answer=f"{name} 리포트는 로그인 후 상세 페이지에서 볼 수 있습니다. 챗봇은 리포트 생성을 자동 실행하지 않습니다.",
            intent="report_help",
            confidence=0.86,
            actions=[login_action("AI 리포트 조회는 로그인이 필요합니다."), detail_action],
            cards=[{"type": "asset", "ticker": ticker, "name": name, "route": f"/detail/{_quote_path(ticker)}"}],
            requires_auth=True,
            disclaimer=DISCLAIMER,
        )

    report = await _fetch_saved_report(ticker, db)
    if report is None:
        return ChatResponse(
            answer=f"{name}에 저장된 최신 AI 리포트를 아직 찾지 못했습니다. 자동 생성은 하지 않으며, 상세 페이지의 리포트 영역에서 상태를 확인할 수 있습니다.",
            intent="report_help",
            confidence=0.82,
            actions=[detail_action],
            cards=[{"type": "asset", "ticker": ticker, "name": name, "route": f"/detail/{_quote_path(ticker)}"}],
            disclaimer=DISCLAIMER,
        )

    summary = _summarize_report(report)
    return ChatResponse(
        answer=f"{name} 저장 리포트 요약입니다. {summary}",
        intent="report_help",
        confidence=0.9,
        actions=[detail_action],
        cards=[{"type": "asset", "ticker": ticker, "name": name, "route": f"/detail/{_quote_path(ticker)}"}],
        disclaimer=DISCLAIMER,
    )


def _community_help_response(candidates: list, current_ticker: str | None, authenticated: bool) -> ChatResponse:
    candidate = candidates[0] if candidates else None
    ticker = candidate.ticker if candidate else current_ticker
    name = candidate.name if candidate else display_name_for_ticker(ticker or "")
    actions = []
    cards = []
    if not authenticated:
        actions.append(login_action("댓글 작성, 좋아요, 신고는 로그인이 필요합니다."))
    if ticker:
        actions.append(
            {
                "type": "navigate",
                "label": f"{name} 토론방 보기",
                "url": f"/detail/{_quote_path(ticker)}",
                "reason": "종목 토론방은 자산 상세 페이지 아래에 있습니다.",
                "confidence": 0.86,
                "requires_auth": False,
            }
        )
        cards.append({"type": "asset", "ticker": ticker, "name": name, "route": f"/detail/{_quote_path(ticker)}"})
        answer = f"{name} 상세 페이지 아래 종목 토론방에서 댓글을 읽을 수 있습니다. 작성, 수정, 삭제, 좋아요, 신고는 로그인이 필요합니다."
    else:
        actions.extend(
            [
                category_action({"label": "미국 주식 TOP10", "route": "/category/us_top10"}, confidence=0.6),
                category_action({"label": "한국 주식 TOP10", "route": "/category/kr_top10"}, confidence=0.6),
                category_action({"label": "암호화폐", "route": "/category/cryptos"}, confidence=0.6),
            ]
        )
        answer = "댓글을 남기려면 먼저 자산 상세 페이지를 열어야 합니다. 댓글 작성과 상호작용은 로그인이 필요합니다."
    return ChatResponse(
        answer=answer,
        intent="community_help",
        confidence=0.84,
        actions=actions,
        cards=cards,
        requires_auth=not authenticated,
        disclaimer=DISCLAIMER,
    )


def _favorite_help_response(candidates: list, current_ticker: str | None) -> ChatResponse:
    candidate = candidates[0] if candidates else None
    ticker = candidate.ticker if candidate else current_ticker
    actions = []
    cards = []
    if ticker:
        name = candidate.name if candidate else display_name_for_ticker(ticker)
        actions.append(
            {
                "type": "navigate",
                "label": f"{name} 상세 페이지 보기",
                "url": f"/detail/{_quote_path(ticker)}",
                "reason": "상세 페이지와 카테고리 목록에서 별 버튼으로 즐겨찾기를 관리할 수 있습니다.",
                "confidence": 0.82,
                "requires_auth": False,
            }
        )
        cards.append({"type": "asset", "ticker": ticker, "name": name, "route": f"/detail/{_quote_path(ticker)}"})
    else:
        actions.append(category_action({"label": "미국 주식 TOP10", "route": "/category/us_top10"}, confidence=0.62))
    return ChatResponse(
        answer="즐겨찾기는 브라우저에 저장됩니다. 카테고리 목록이나 자산 상세 화면의 별 버튼으로 추가하고 해제할 수 있습니다.",
        intent="favorite_help",
        confidence=0.82,
        actions=actions,
        cards=cards,
        disclaimer=DISCLAIMER,
    )


def _current_page_response(current_path: str, current_ticker: str | None, authenticated: bool) -> ChatResponse:
    if current_ticker:
        name = display_name_for_ticker(current_ticker)
        actions = [
            {
                "type": "navigate",
                "label": f"{name} 상세 페이지 보기",
                "url": f"/detail/{_quote_path(current_ticker)}",
                "reason": "현재 자산 맥락을 유지합니다.",
                "confidence": 0.8,
                "requires_auth": False,
            }
        ]
        answer = (
            f"현재 화면은 {name} 관련 화면입니다. 가격, 차트, 최신 뉴스, AI 리포트와 커뮤니티를 확인할 수 있으며 "
            f"AI 리포트 조회와 댓글 작성은 {'현재 로그인 상태에서 사용할 수 있습니다' if authenticated else '로그인 후 사용할 수 있습니다'}."
        )
    elif current_path.startswith("/category/"):
        answer = "현재 화면은 자산군 목록입니다. 관심 있는 자산을 선택하면 상세 페이지, 리포트, 커뮤니티로 이동할 수 있습니다."
        actions = []
    elif current_path == "/login":
        answer = "현재 화면은 Google 로그인 화면입니다. 로그인하면 리포트 조회와 커뮤니티 상호작용을 사용할 수 있습니다."
        actions = []
    else:
        answer = "현재 화면은 홈입니다. 주요 지수와 환율, 글로벌 뉴스, 자산군 목록으로 이동할 수 있습니다."
        actions = [category_action({"label": "주요 지수·환율", "route": "/category/macro"}, confidence=0.65)]
    return ChatResponse(
        answer=answer,
        intent="current_page_help",
        confidence=0.76,
        actions=actions,
        disclaimer=DISCLAIMER,
    )


async def _market_summary_response(candidates: list, current_ticker: str | None) -> ChatResponse:
    ticker = candidates[0].ticker if candidates else current_ticker
    if ticker:
        name = candidates[0].name if candidates else display_name_for_ticker(ticker)
        context = await fetch_latest_asset_context(ticker, force_refresh=False)
        news = context.get("news") or []
        events = context.get("events") or []
        headlines = [item.get("title") for item in news[:3] if item.get("title")]
        event_titles = [item.get("title") for item in events[:2] if item.get("title")]
        pieces = []
        if headlines:
            pieces.append("최근 뉴스: " + " / ".join(headlines))
        if event_titles:
            pieces.append("확인된 일정: " + " / ".join(event_titles))
        if not pieces:
            pieces.append("현재 캐시에서 확인된 최신 뉴스나 발표 일정이 없습니다.")
        pieces.append(f"데이터 상태: {context.get('source_status', 'unknown')}")
        return ChatResponse(
            answer=f"{name} 최신 컨텍스트입니다. " + " ".join(pieces),
            intent="market_summary",
            confidence=0.78,
            actions=[
                {
                    "type": "navigate",
                    "label": f"{name} 상세 페이지 보기",
                    "url": f"/detail/{_quote_path(ticker)}",
                    "reason": "상세 페이지에서 뉴스와 발표 일정을 더 확인할 수 있습니다.",
                    "confidence": 0.82,
                    "requires_auth": False,
                }
            ],
            cards=[{"type": "asset", "ticker": ticker, "name": name, "route": f"/detail/{_quote_path(ticker)}"}],
            disclaimer=DISCLAIMER,
        )

    macro = (market_cache.get("prices") or {}).get("macro") or {}
    if not macro:
        answer = "현재 시장 요약 캐시가 비어 있습니다. 홈 화면에서 주요 지수와 환율 카드를 확인해 주세요."
    else:
        lines = []
        for label, payload in list(macro.items())[:4]:
            change = payload.get("changePercent", payload.get("change_pct", 0))
            lines.append(f"{label}: {float(change or 0):+.2f}%")
        updated = (market_cache.get("last_updated") or {}).get("prices")
        answer = "캐시 기준 주요 시장 흐름입니다. " + ", ".join(lines)
        if updated:
            answer += f" 기준 시각: {updated}."
    return ChatResponse(
        answer=answer,
        intent="market_summary",
        confidence=0.72,
        actions=[
            category_action({"label": "주요 지수·환율", "route": "/category/macro"}, confidence=0.78),
            {
                "type": "navigate",
                "label": "홈에서 시장 카드 보기",
                "url": "/",
                "reason": "홈 화면에서 주요 지수와 글로벌 뉴스를 볼 수 있습니다.",
                "confidence": 0.7,
                "requires_auth": False,
            },
        ],
        disclaimer=DISCLAIMER,
    )


async def _fetch_saved_report(ticker: str, db: AsyncSession) -> AIReport | None:
    query = (
        select(AIReport)
        .join(Asset, AIReport.asset_id == Asset.id)
        .where(Asset.ticker == ticker)
        .order_by(AIReport.created_at.desc())
        .limit(1)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


def _summarize_report(report: AIReport) -> str:
    parts = []
    metadata = report.metadata_json or {}
    packet = metadata.get("research_packet") or {}
    base_items = _packet_items(packet.get("base_case"))
    risk_items = _packet_items(packet.get("risk_review"))
    if base_items:
        parts.append(f"Base case: {_clean_text(base_items[0], 90)}")
    if risk_items:
        parts.append(f"Risk review: {_clean_text(risk_items[0], 90)}")
    if report.bull_summary:
        parts.append(f"상승 관점: {_clean_text(report.bull_summary, 90)}")
    if report.bear_summary:
        parts.append(f"리스크 관점: {_clean_text(report.bear_summary, 90)}")
    risk_summary = metadata.get("risk_summary") or report.risk_summary
    if risk_summary:
        parts.append(f"주의점: {_clean_text(str(risk_summary), 90)}")
    if not parts:
        parts.append(_clean_text(report.final_content, 180))
    data_as_of = metadata.get("data_as_of") or (report.data_as_of.isoformat() if report.data_as_of else None)
    if data_as_of:
        parts.append(f"데이터 기준: {data_as_of}")
    return " ".join(parts)


def _packet_items(block: Any) -> list[str]:
    if not isinstance(block, dict):
        return []
    items = block.get("items")
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _clean_text(value: str, limit: int) -> str:
    text = re.sub(r"[#*_>`-]+", " ", value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _context_ticker(current_path: str, context: ChatContext) -> str | None:
    if context.ticker:
        return context.ticker
    path = current_path or ""
    for prefix in ("/detail/", "/market/"):
        if path.startswith(prefix):
            return unquote(path.removeprefix(prefix)).strip() or None
    return None


def _looks_like_category_request(message: str) -> bool:
    normalized = message.lower()
    return any(keyword in normalized for keyword in ["목록", "전체", "종류", "top", "모아", "자산군"])


def _is_ambiguous(message: str) -> bool:
    normalized = message.lower()
    return any(keyword in normalized for keyword in ["보여줘", "보고 싶", "알려줘", "목록", "채권", "삼성"])


def _quote_path(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")

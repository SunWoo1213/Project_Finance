import pytest

from app.core.config import settings
from app.services import chat_llm
from app.services.chat_llm import ALLOWED_INTENTS, LlmChatPlan, compose_chat_answer


def test_allowed_intents_have_no_report_generation_intent():
    # The chatbot must never generate reports; there is no generate-style intent.
    assert not any("generate" in intent for intent in ALLOWED_INTENTS)
    assert "report_help" in ALLOWED_INTENTS


@pytest.mark.asyncio
async def test_compose_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_LLM_CHATBOT", False)
    result = await compose_chat_answer(message="삼성전자 어때", history=[], grounding={})
    assert result is None


@pytest.mark.asyncio
async def test_compose_returns_none_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_LLM_CHATBOT", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    result = await compose_chat_answer(message="삼성전자 어때", history=[], grounding={})
    assert result is None


@pytest.mark.asyncio
async def test_compose_validates_intent_and_clamps_indices(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_LLM_CHATBOT", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    class FakeStructuredLLM:
        async def ainvoke(self, _messages):
            # Invalid intent and an out-of-range action index.
            return LlmChatPlan(
                answer="삼성전자 관련 정보를 안내합니다.",
                intent="totally_made_up",
                confidence=0.8,
                action_indices=[5, 0],
            )

    monkeypatch.setattr(chat_llm, "_get_structured_llm", lambda: FakeStructuredLLM())

    grounding = {"actions": [{"label": "삼성전자 상세 보기"}]}
    plan = await compose_chat_answer(message="삼성전자 어때", history=[], grounding=grounding)

    assert plan is not None
    assert plan.intent == "unknown"  # invalid intent normalized
    assert plan.action_indices == [0]  # out-of-range index dropped


@pytest.mark.asyncio
async def test_compose_falls_back_to_none_on_llm_error(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_LLM_CHATBOT", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    def _boom():
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(chat_llm, "_get_structured_llm", _boom)

    plan = await compose_chat_answer(message="삼성전자 어때", history=[], grounding={"actions": []})
    assert plan is None

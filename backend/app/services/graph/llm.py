from langchain_openai import ChatOpenAI

from ...core.config import settings


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=settings.OPENAI_API_KEY,
    )

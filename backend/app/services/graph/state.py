from typing import Any, TypedDict


class AgentState(TypedDict):
    ticker: str
    category: str
    price_data: dict[str, Any]
    news_data: list[dict[str, Any]]
    asset_category: str

    # Parallel research contexts
    financial_context: str
    news_context: str
    macro_context: str

    # Pipeline fields
    structured_facts: dict[str, Any]
    draft_report: str
    previous_report: str
    feedback: str
    revision_count: int

    # Backward compatibility fields used by service layer
    analysis_result: str
    final_report: str
    retry_count: int
    is_pass: bool

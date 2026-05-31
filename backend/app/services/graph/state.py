from typing import Any, TypedDict


class AgentState(TypedDict):
    ticker: str
    category: str
    price_data: dict[str, Any]
    news_data: list[dict[str, Any]]
    latest_context: dict[str, Any]
    asset_category: str
    report_facts: dict[str, Any]
    generation_metadata: dict[str, Any]

    # Parallel research contexts
    financial_context: str
    news_context: str
    macro_context: str
    financial_facts: dict[str, Any]
    news_facts: dict[str, Any]
    macro_facts: dict[str, Any]

    # Pipeline fields
    structured_facts: dict[str, Any]
    bull_thesis: dict[str, Any]
    bear_thesis: dict[str, Any]
    risk_review: dict[str, Any]
    draft_report: str
    format_check_pass: bool
    format_check_feedback: str
    fact_check_pass: bool
    fact_check_feedback: str
    qualitative_check_pass: bool
    qualitative_check_feedback: str
    previous_report: str
    feedback: str
    revision_count: int

    # Backward compatibility fields used by service layer
    analysis_result: str
    final_report: str
    retry_count: int
    is_pass: bool

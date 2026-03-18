from typing import TypedDict


class AgentState(TypedDict):
    ticker: str
    price_data: dict
    news_data: list
    bull_analysis: str
    bear_analysis: str
    final_report: str

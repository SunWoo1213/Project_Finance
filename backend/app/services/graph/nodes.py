from langchain_core.prompts import ChatPromptTemplate

from .llm import get_llm
from .state import AgentState


def bull_agent(state: AgentState) -> dict:
    prompt = ChatPromptTemplate.from_template(
        "너는 월스트리트의 극단적인 강세장(Bull) 애널리스트야. "
        "주어진 종목({ticker}), 가격/등락률({price_data}), 최신 뉴스({news_data})를 보고, "
        "무조건 이 자산을 지금 당장 매수해야 하는 이유와 호재만 3~4문장으로 강력하게 어필해."
    )
    llm = get_llm()
    chain = prompt | llm
    result = chain.invoke(
        {
            "ticker": state["ticker"],
            "price_data": state["price_data"],
            "news_data": state["news_data"],
        }
    )
    return {"bull_analysis": result.content}


def bear_agent(state: AgentState) -> dict:
    prompt = ChatPromptTemplate.from_template(
        "너는 매우 보수적이고 깐깐한 리스크 관리자(Bear)야. "
        "주어진 데이터를 바탕으로 이 자산의 거품, 위험 요소, 매도해야 하는 이유만 "
        "3~4문장으로 날카롭게 지적해."
        "\n종목: {ticker}\n가격/등락률: {price_data}\n최신 뉴스: {news_data}"
    )
    llm = get_llm()
    chain = prompt | llm
    result = chain.invoke(
        {
            "ticker": state["ticker"],
            "price_data": state["price_data"],
            "news_data": state["news_data"],
        }
    )
    return {"bear_analysis": result.content}


def synthesizer_agent(state: AgentState) -> dict:
    prompt = ChatPromptTemplate.from_template(
        "너는 수석 투자 책임자(CIO)야. "
        "Bull의 의견({bull_analysis})과 Bear의 의견({bear_analysis}), "
        "그리고 팩트 데이터({price_data}, {news_data})가 모두 주어졌어. "
        "이를 객관적으로 종합하여 일반 투자자가 읽기 쉬운 깔끔한 마크다운 형식의 최종 투자 리포트를 작성해. "
        "마지막에는 반드시 [Strong Buy / Buy / Hold / Sell / Strong Sell] 중 하나의 투자 등급(Verdict)을 명시해."
    )
    llm = get_llm()
    chain = prompt | llm
    result = chain.invoke(
        {
            "bull_analysis": state["bull_analysis"],
            "bear_analysis": state["bear_analysis"],
            "price_data": state["price_data"],
            "news_data": state["news_data"],
        }
    )
    return {"final_report": result.content}

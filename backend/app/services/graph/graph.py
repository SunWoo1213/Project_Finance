from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from .nodes import (
    bear_agent_node,
    bull_agent_node,
    evaluator_node,
    fact_checker_node,
    financial_agent,
    macro_agent,
    news_agent,
    qualitative_claim_checker_node,
    report_format_validator_node,
    research_packet_node,
    risk_officer_node,
    synthesizer_node,
    writer_node,
)
from .state import AgentState


def route_fact_check(state: AgentState) -> str:
    revision_count = state.get("revision_count", 0)

    if state.get("fact_check_pass"):
        return "qualitative_claim_checker_node"
    if revision_count >= 3:
        return "END"
    return "writer_node"


def route_qualitative_check(state: AgentState) -> str:
    revision_count = state.get("revision_count", 0)

    if state.get("qualitative_check_pass"):
        return "evaluator_node"
    if revision_count >= 3:
        return "END"
    return "writer_node"


def route_format_check(state: AgentState) -> str:
    revision_count = state.get("revision_count", 0)

    if state.get("format_check_pass"):
        return "fact_checker_node"
    if revision_count >= 3:
        return "END"
    return "writer_node"


def route_evaluation(state: AgentState) -> str:
    revision_count = state.get("revision_count", 0)

    if state.get("is_pass") or revision_count >= 3:
        return "END"
    return "writer_node"


workflow = StateGraph(AgentState)

workflow.add_node("financial_agent", financial_agent)
workflow.add_node("news_agent", news_agent)
workflow.add_node("macro_agent", macro_agent)
workflow.add_node("synthesizer_node", synthesizer_node)
workflow.add_node("bull_agent_node", bull_agent_node)
workflow.add_node("bear_agent_node", bear_agent_node)
workflow.add_node("risk_officer_node", risk_officer_node)
workflow.add_node("research_packet_node", research_packet_node)
workflow.add_node("writer_node", writer_node)
workflow.add_node("report_format_validator_node", report_format_validator_node)
workflow.add_node("fact_checker_node", fact_checker_node)
workflow.add_node("qualitative_claim_checker_node", qualitative_claim_checker_node)
workflow.add_node("evaluator_node", evaluator_node)

# 1) Parallel branches from START
workflow.add_edge(START, "financial_agent")
workflow.add_edge(START, "news_agent")
workflow.add_edge(START, "macro_agent")

# 2) Join branches to synthesizer
workflow.add_edge(["financial_agent", "news_agent", "macro_agent"], "synthesizer_node")

# 3) Separate structured facts into scenario and risk views
workflow.add_edge("synthesizer_node", "bull_agent_node")
workflow.add_edge("synthesizer_node", "bear_agent_node")
workflow.add_edge("synthesizer_node", "risk_officer_node")
workflow.add_edge(["bull_agent_node", "bear_agent_node", "risk_officer_node"], "research_packet_node")
workflow.add_edge("research_packet_node", "writer_node")

# 4) Write/evaluate loop
workflow.add_edge("writer_node", "report_format_validator_node")
workflow.add_conditional_edges(
    "report_format_validator_node",
    route_format_check,
    {
        "END": END,
        "writer_node": "writer_node",
        "fact_checker_node": "fact_checker_node",
    },
)
workflow.add_conditional_edges(
    "fact_checker_node",
    route_fact_check,
    {
        "END": END,
        "writer_node": "writer_node",
        "qualitative_claim_checker_node": "qualitative_claim_checker_node",
    },
)
workflow.add_conditional_edges(
    "qualitative_claim_checker_node",
    route_qualitative_check,
    {
        "END": END,
        "writer_node": "writer_node",
        "evaluator_node": "evaluator_node",
    },
)
workflow.add_conditional_edges(
    "evaluator_node",
    route_evaluation,
    {
        "END": END,
        "writer_node": "writer_node",
    },
)

memory = MemorySaver()
graph_app = workflow.compile(checkpointer=memory)
app = graph_app

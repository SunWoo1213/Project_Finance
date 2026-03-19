from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from .nodes import evaluator_node, financial_agent, macro_agent, news_agent, synthesizer_node, writer_node
from .state import AgentState


def route_evaluation(state: AgentState) -> str:
    feedback = state.get("feedback", "")
    revision_count = state.get("revision_count", 0)

    if "PASS" in str(feedback).upper() or revision_count >= 3:
        return "END"
    return "writer_node"


workflow = StateGraph(AgentState)

workflow.add_node("financial_agent", financial_agent)
workflow.add_node("news_agent", news_agent)
workflow.add_node("macro_agent", macro_agent)
workflow.add_node("synthesizer_node", synthesizer_node)
workflow.add_node("writer_node", writer_node)
workflow.add_node("evaluator_node", evaluator_node)

# 1) Parallel branches from START
workflow.add_edge(START, "financial_agent")
workflow.add_edge(START, "news_agent")
workflow.add_edge(START, "macro_agent")

# 2) Join branches to synthesizer
workflow.add_edge(["financial_agent", "news_agent", "macro_agent"], "synthesizer_node")

# 3) Write/evaluate loop
workflow.add_edge("synthesizer_node", "writer_node")
workflow.add_edge("writer_node", "evaluator_node")
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

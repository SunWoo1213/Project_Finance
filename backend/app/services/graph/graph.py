from langgraph.graph import END, START, StateGraph

from .nodes import bear_agent, bull_agent, synthesizer_agent
from .state import AgentState

workflow = StateGraph(AgentState)

workflow.add_node("bull", bull_agent)
workflow.add_node("bear", bear_agent)
workflow.add_node("synthesizer", synthesizer_agent)

workflow.add_edge(START, "bull")
workflow.add_edge("bull", "bear")
workflow.add_edge("bear", "synthesizer")
workflow.add_edge("synthesizer", END)

app = workflow.compile()

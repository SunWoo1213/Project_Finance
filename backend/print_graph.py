from app.services.graph.graph import app as graph_app

print("\n=== LangGraph Mermaid Diagram ===")
print(graph_app.get_graph().draw_mermaid())
print("=================================\n")

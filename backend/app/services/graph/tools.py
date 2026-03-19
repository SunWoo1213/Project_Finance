from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchResults

# Initialize the search tool
search_tool = DuckDuckGoSearchResults()
search_tool.name = "search_tool"
search_tool.description = "A wrapper around DuckDuckGo Search. Useful for when you need to answer questions about current events or look up specific facts on the internet. Input should be a search query."

@tool
def calculator_tool(expression: str) -> str:
    """Calculate the result of a mathematical expression. Input the mathematical formula as a string (e.g. '150 * 1.2')."""
    try:
        # Warning: eval is used here simply for the clone scope. In production, use numexpr or ast.literal_eval.
        allowed_chars = set("0123456789+-*/(). ")
        if not all(c in allowed_chars for c in expression):
            return "Error: Invalid characters in expression."
        
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Error computing expression: {e}"

tools = [search_tool, calculator_tool]

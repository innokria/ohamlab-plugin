"""Initial bounded research workflow. Autonomous planning comes in a later phase."""
from mcp_server.tools.search import search_and_fetch


def run_research_task(query: str, max_results: int = 5, fetch_top: int = 3) -> dict:
    """Search, fetch a bounded number of pages, and persist extracted content."""
    return search_and_fetch(query, max_results, fetch_top)

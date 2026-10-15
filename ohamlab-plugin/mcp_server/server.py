
"""MCP tools exposed by ohamlab-plugin."""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from mcp_server.tools.search import web_search, search_and_fetch
from browser.automation import fetch_page
from storage.bucket import store


mcp = FastMCP(
    "OhamLab",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "rahul7star-ohamlab-plugin.hf.space",
            "rahul7star-ohamlab-plugin.hf.space:443",
        ],
        allowed_origins=[
            "https://rahul7star-ohamlab-plugin.hf.space",
        ],
    ),
)


@mcp.tool()
def web_search_tool(query: str, max_results: int = 5) -> dict:
    """Search public web indexes and return titles, URLs, and snippets."""
    try:
        return {
            "ok": True,
            "query": query,
            "results": web_search(query, max_results),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:1000], "results": []}


@mcp.tool()
def web_fetch(url: str, save: bool = True) -> dict:
    """Fetch a public webpage and optionally save its extracted text."""
    try:
        document = fetch_page(url, save=save)
        result = dict(document)
        result["text"] = result.get("text", "")[:12000]
        return {"ok": True, "document": result}
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)[:1000]}


@mcp.tool()
def search_and_fetch_tool(
    query: str,
    max_results: int = 5,
    fetch_top: int = 3,
) -> dict:
    """Search the web, fetch top results, and store extracted documents."""
    return search_and_fetch(query, max_results, fetch_top)


@mcp.tool()
def stored_documents(query: str = "", limit: int = 10) -> dict:
    """List saved document metadata and snippets, optionally filtered by query."""
    return {"documents": store.list_documents(query, max(1, min(limit, 100)))}


@mcp.tool()
def get_document(document_id: str) -> dict:
    """Retrieve a saved document by ID, including its extracted text."""
    document = store.get_document(document_id)
    if document is None:
        return {
            "ok": False,
            "error": "document_not_found",
            "document_id": document_id,
        }
    return {"ok": True, "document": document}


@mcp.tool()
def task_history(limit: int = 20) -> dict:
    """Retrieve recent search, fetch, and storage task history."""
    return {"tasks": store.task_history(max(1, min(limit, 100)))}


"""MCP tools exposed by OhamLab Plugin."""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from mcp_server.tools.search import web_search, search_and_fetch
from browser.automation import fetch_page
from storage.bucket import store


SPACE_HOST = "rahul7star-ohamlab-plugin.hf.space"

mcp = FastMCP(
    "OhamLab",
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            SPACE_HOST,
            f"{SPACE_HOST}:443",
        ],
        allowed_origins=[
            f"https://{SPACE_HOST}",
        ],
    ),
)


@mcp.tool()
def web_search_tool(query: str, max_results: int = 5) -> dict:
    """Search public web indexes and return titles, URLs, and snippets."""
    try:
        max_results = max(1, min(max_results, 10))

        return {
            "ok": True,
            "query": query,
            "results": web_search(query, max_results),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:1000],
            "results": [],
        }


@mcp.tool()
def web_fetch(url: str, save: bool = True) -> dict:
    """Fetch a public webpage and optionally save its extracted text."""
    try:
        document = fetch_page(url, save=save)
        result = dict(document)
        result["text"] = str(result.get("text", ""))[:12000]

        return {
            "ok": True,
            "document": result,
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "error": str(exc)[:1000],
        }


@mcp.tool()
def search_and_fetch_tool(
    query: str,
    max_results: int = 5,
    fetch_top: int = 3,
) -> dict:
    """Search the web, fetch top results, and store extracted documents."""
    try:
        max_results = max(1, min(max_results, 10))
        fetch_top = max(0, min(fetch_top, max_results))

        return search_and_fetch(
            query,
            max_results,
            fetch_top,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:1000],
        }


@mcp.tool()
def stored_documents(query: str = "", limit: int = 10) -> dict:
    """List saved document metadata and snippets, optionally filtered by query."""
    try:
        limit = max(1, min(limit, 100))

        return {
            "ok": True,
            "documents": store.list_documents(query, limit),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:1000],
            "documents": [],
        }


@mcp.tool()
def get_document(document_id: str) -> dict:
    """Retrieve a saved document by ID, including its extracted text."""
    try:
        document = store.get_document(document_id)

        if document is None:
            return {
                "ok": False,
                "error": "document_not_found",
                "document_id": document_id,
            }

        return {
            "ok": True,
            "document": document,
        }
    except Exception as exc:
        return {
            "ok": False,
            "document_id": document_id,
            "error": str(exc)[:1000],
        }


@mcp.tool()
def task_history(limit: int = 20) -> dict:
    """Retrieve recent search, fetch, and storage task history."""
    try:
        limit = max(1, min(limit, 100))

        return {
            "ok": True,
            "tasks": store.task_history(limit),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:1000],
            "tasks": [],
        }

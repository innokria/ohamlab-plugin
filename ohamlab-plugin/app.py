"""OhamLab Plugin: Gradio UI, FastAPI endpoints, and MCP server."""

import os
import secrets

import gradio as gr
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from mcp_server.server import mcp
from mcp_server.tools.search import search_and_fetch
from browser.automation import fetch_page
from storage.bucket import store


# =========================================================
# FastAPI application
# =========================================================

app = FastAPI(
    title="OhamLab Plugin",
    version="0.1.0",
)


# =========================================================
# Authentication using HF_TOKEN
# =========================================================

def _authorized(request: Request) -> bool:
    """Validate an incoming Bearer token against HF_TOKEN."""
    expected = os.getenv("HF_TOKEN", "").strip()

    # Hosted deployments must configure HF_TOKEN.
    # Local development can run without authentication.
    if not expected:
        return not bool(os.getenv("SPACE_ID"))

    supplied = request.headers.get("authorization", "")

    return secrets.compare_digest(
        supplied,
        f"Bearer {expected}",
    )


@app.middleware("http")
async def protect_endpoints(request: Request, call_next):
    """Protect MCP and document API endpoints."""
    path = request.url.path

    protected = (
        path == "/mcp"
        or path.startswith("/mcp/")
        or path == "/api/documents"
        or path.startswith("/api/documents/")
    )

    if protected and not _authorized(request):
        return JSONResponse(
            status_code=401,
            content={"detail": "unauthorized"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)


# =========================================================
# Health endpoint
# =========================================================

@app.get("/health")
async def health():
    """Public health check."""
    return {
        "status": "ok",
        "service": "ohamlab-plugin",
    }


# =========================================================
# Documents API
# =========================================================

@app.get("/api/documents")
async def api_documents(
    q: str = "",
    limit: int = 10,
):
    """List stored documents. Authentication is enforced by middleware."""
    documents = store.list_documents(
        q,
        max(1, min(limit, 100)),
    )

    return {"documents": documents}


# =========================================================
# MCP endpoint
# =========================================================

# Expose the Streamable HTTP MCP server under /mcp.
# The client URL will be https://YOUR-SPACE.hf.space/mcp
app.mount(
    "/mcp",
    mcp.streamable_http_app(),
)


# =========================================================
# Gradio UI handlers
# =========================================================

def ui_search(query, max_results, fetch_top):
    """Search the web and optionally fetch and store top results."""
    if not query or not query.strip():
        return "Enter a search query.", ""

    try:
        result = search_and_fetch(
            query.strip(),
            int(max_results),
            int(fetch_top),
        )

        search_md = "\n\n---\n\n".join(
            f"### {item.get('title') or item['url']}\n"
            f"{item['url']}\n\n"
            f"{item.get('snippet', '')}"
            for item in result.get("search_results", [])
        ) or "No search results."

        saved_md = "\n\n".join(
            f"- **{item.get('title', 'Untitled')}** "
            f"— `{item.get('document_id', '')}`\n"
            f"  - {item.get('url', '')}\n"
            f"  - {item.get('content_length', 0)} characters saved"
            for item in result.get("saved_documents", [])
        ) or "No pages saved."

        if result.get("errors"):
            saved_md += "\n\n### Fetch errors\n" + "\n".join(
                f"- {item.get('url', '')}: {item.get('error', 'Unknown error')}"
                for item in result["errors"]
            )

        if not result.get("ok"):
            saved_md = result.get("error", "Search failed.")

        return search_md, saved_md

    except Exception as exc:
        return "Search failed.", str(exc)


def ui_fetch(url):
    """Fetch a URL, extract readable text, and save the document."""
    if not url or not url.strip():
        return "Enter a URL."

    try:
        document = fetch_page(url.strip(), save=True)

        return (
            f"# {document.get('title', 'Fetched document')}\n\n"
            f"URL: {document.get('url', url)}\n\n"
            f"Document ID: `{document.get('document_id', '')}`\n\n"
            f"## Extracted text\n\n"
            f"{document.get('text', '')[:12000]}"
        )

    except Exception as exc:
        return f"Fetch failed: {exc}"


def ui_documents(query, limit):
    """Show documents stored by OhamLab."""
    try:
        documents = store.list_documents(
            query or "",
            max(1, min(int(limit), 100)),
        )

        return "\n\n---\n\n".join(
            f"### {doc.get('title') or doc.get('url', 'Untitled')}\n"
            f"ID: `{doc.get('document_id', '')}`\n"
            f"URL: {doc.get('url', '')}\n\n"
            f"{doc.get('snippet', '')}"
            for doc in documents
        ) or "No saved documents."

    except Exception as exc:
        return f"Could not load documents: {exc}"


# =========================================================
# Gradio interface
# =========================================================

with gr.Blocks(title="OhamLab Plugin") as demo:
    gr.Markdown(
        "# OhamLab Plugin\n"
        "Search websites, extract readable content, and store documents "
        "for use by DeepSeek Harness through MCP."
    )

    with gr.Tab("Search → Fetch → Store"):
        query = gr.Textbox(
            label="Search query",
            placeholder="Hugging Face MCP documentation",
        )

        with gr.Row():
            max_results = gr.Slider(
                minimum=1,
                maximum=10,
                value=5,
                step=1,
                label="Maximum search results",
            )

            fetch_top = gr.Slider(
                minimum=0,
                maximum=5,
                value=3,
                step=1,
                label="Pages to fetch and store",
            )

        run_button = gr.Button(
            "Search, fetch and store",
            variant="primary",
        )

        search_results = gr.Markdown()
        saved_results = gr.Markdown()

        run_button.click(
            fn=ui_search,
            inputs=[query, max_results, fetch_top],
            outputs=[search_results, saved_results],
        )

    with gr.Tab("Fetch URL"):
        url = gr.Textbox(
            label="Public website URL",
            placeholder="https://example.com",
        )

        fetch_button = gr.Button(
            "Fetch and store",
            variant="primary",
        )

        fetched_output = gr.Markdown()

        fetch_button.click(
            fn=ui_fetch,
            inputs=[url],
            outputs=[fetched_output],
        )

    with gr.Tab("Stored documents"):
        filter_query = gr.Textbox(
            label="Filter documents",
            placeholder="Search titles, URLs, or snippets",
        )

        document_limit = gr.Slider(
            minimum=1,
            maximum=50,
            value=10,
            step=1,
            label="Maximum documents",
        )

        list_button = gr.Button("Load documents")
        documents_output = gr.Markdown()

        list_button.click(
            fn=ui_documents,
            inputs=[filter_query, document_limit],
            outputs=[documents_output],
        )


# IMPORTANT:
# Register FastAPI routes and mount MCP before mounting Gradio at "/".
# Gradio must be mounted last to avoid intercepting /health and API routes.
app = gr.mount_gradio_app(
    app,
    demo,
    path="/",
)

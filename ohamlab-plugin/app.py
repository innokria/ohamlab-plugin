"""Gradio test UI and FastAPI host for the MCP service."""
import os
import gradio as gr
from fastapi import FastAPI, Request, HTTPException
from mcp_server.server import mcp
from mcp_server.tools.search import search_and_fetch
from browser.automation import fetch_page
from storage.bucket import store

app = FastAPI(title="OhamLab Plugin", version="0.1.0")
app.mount("/mcp", mcp.streamable_http_app())


def ui_search(query, max_results, fetch_top):
    if not query or not query.strip():
        return "Enter a search query.", ""
    result = search_and_fetch(query.strip(), int(max_results), int(fetch_top))
    search_md = "\n\n---\n\n".join(
        f"### {item.get('title') or item['url']}\n{item['url']}\n\n{item.get('snippet', '')}"
        for item in result.get("search_results", [])
    ) or "No search results."
    saved_md = "\n\n".join(
        f"- **{item['title']}** — `{item['document_id']}`\n  - {item['url']}\n  - {item['content_length']} characters saved"
        for item in result.get("saved_documents", [])
    ) or "No pages saved."
    if result.get("errors"):
        saved_md += "\n\nFetch errors:\n" + "\n".join(f"- {x['url']}: {x['error']}" for x in result['errors'])
    if not result.get("ok"):
        saved_md = result.get("error", "Search failed")
    return search_md, saved_md


def ui_fetch(url):
    if not url or not url.strip():
        return "Enter a URL."
    try:
        document = fetch_page(url.strip(), save=True)
        return (
            f"# {document['title']}\n\nURL: {document['url']}\n\n"
            f"Document ID: `{document['document_id']}`\n\n"
            f"## Extracted text\n\n{document['text'][:12000]}"
        )
    except Exception as exc:
        return f"Fetch failed: {exc}"


def ui_documents(query, limit):
    documents = store.list_documents(query or "", int(limit))
    return "\n\n---\n\n".join(
        f"### {doc.get('title') or doc['url']}\nID: `{doc['document_id']}`\nURL: {doc['url']}\n\n{doc.get('snippet', '')}"
        for doc in documents
    ) or "No saved documents."


with gr.Blocks(title="OhamLab Plugin") as demo:
    gr.Markdown(
        "# OhamLab Plugin\nSearch websites, extract readable content, and store source-backed documents for DeepSeek Harness."
    )
    with gr.Tab("Search → Fetch → Store"):
        query = gr.Textbox(label="Search query", placeholder="Hugging Face Storage Bucket documentation")
        with gr.Row():
            max_results = gr.Slider(1, 10, value=5, step=1, label="Search results")
            fetch_top = gr.Slider(0, 5, value=3, step=1, label="Fetch top results")
        run_button = gr.Button("Search, fetch and store", variant="primary")
        search_results = gr.Markdown()
        saved_results = gr.Markdown()
        run_button.click(ui_search, [query, max_results, fetch_top], [search_results, saved_results])
    with gr.Tab("Fetch URL"):
        url = gr.Textbox(label="Public website URL", placeholder="https://example.com")
        fetch_button = gr.Button("Fetch and store", variant="primary")
        fetched_output = gr.Markdown()
        fetch_button.click(ui_fetch, [url], fetched_output)
    with gr.Tab("Stored documents"):
        filter_query = gr.Textbox(label="Filter by title, URL, description, or snippet")
        limit = gr.Slider(1, 50, value=10, step=1, label="Maximum documents")
        list_button = gr.Button("Load documents")
        documents_output = gr.Markdown()
        list_button.click(ui_documents, [filter_query, limit], documents_output)

app = gr.mount_gradio_app(app, demo, path="/")


def _authorized(request: Request) -> bool:
    expected = os.getenv("OHAM_MCP_API_KEY", "").strip()
    if not expected:
        # Local development only. A hosted Space must set a secret.
        return not bool(os.getenv("SPACE_ID"))
    return request.headers.get("authorization", "") == f"Bearer {expected}"


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ohamlab-plugin"}


@app.get("/api/documents")
async def api_documents(request: Request, q: str = "", limit: int = 10):
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="unauthorized")
    return {"documents": store.list_documents(q, max(1, min(limit, 100)))}

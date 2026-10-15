
import os
import secrets
from pathlib import Path
from contextlib import asynccontextmanager

import gradio as gr
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from mcp_server.server import mcp


# --------------------------------------------------
# Configuration
# --------------------------------------------------

STORAGE_DIR = Path(
    os.getenv("DOCUMENT_STORAGE_DIR", "/data/ohamlab-plugin-storage")
).resolve()

SPACE_HOST = os.getenv(
    "SPACE_HOST",
    "rahul7star-ohamlab-plugin.hf.space",
)

SUPPORTED_TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".json",
    ".csv", ".xml", ".html", ".htm", ".yaml", ".yml",
    ".py", ".js", ".ts", ".sql",
}

# --------------------------------------------------
# MCP lifecycle
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="OhamLab Plugin",
    version="0.1.0",
    lifespan=lifespan,
)


# --------------------------------------------------
# Authentication
# --------------------------------------------------

def _authorized(request: Request) -> bool:
    expected = os.getenv("OHAM_MCP_API_KEY", "").strip()

    if not expected:
        expected = os.getenv("HF_TOKEN", "").strip()

    # Require a configured key in a deployed Space.
    if not expected:
        return not bool(os.getenv("SPACE_ID"))

    supplied = request.headers.get("authorization", "")
    scheme, _, token = supplied.partition(" ")

    return (
        scheme.lower() == "bearer"
        and bool(token)
        and secrets.compare_digest(token, expected)
    )


@app.middleware("http")
async def protect_private_endpoints(request: Request, call_next):
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
            content={"detail": "Unauthorized"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)


# --------------------------------------------------
# Mounted bucket storage
# --------------------------------------------------

def list_documents(query: str = "") -> list[dict]:
    """
    Read files from the mounted storage directory.
    Returns paths relative to the storage root.
    """
    if not STORAGE_DIR.is_dir():
        raise RuntimeError(
            f"Document storage directory is unavailable: {STORAGE_DIR}"
        )

    query = query.strip().casefold()
    documents = []

    for path in STORAGE_DIR.rglob("*"):
        try:
            if not path.is_file() or path.is_symlink():
                continue

            relative_path = path.relative_to(STORAGE_DIR).as_posix()

            if query and query not in relative_path.casefold():
                continue

            stat = path.stat()

            documents.append({
                "name": path.name,
                "path": relative_path,
                "extension": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
                "searchable_as_text": (
                    path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS
                ),
            })

        except (OSError, ValueError):
            # Ignore individual files that disappear or cannot be read.
            continue

    return sorted(documents, key=lambda item: item["path"].casefold())


# --------------------------------------------------
# Health and document API
# --------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "storage_dir": str(STORAGE_DIR),
        "storage_exists": STORAGE_DIR.is_dir(),
    }


@app.get("/api/documents")
async def documents_api(request: Request, q: str = ""):
    try:
        documents = list_documents(q)
        return {
            "documents": documents,
            "count": len(documents),
            "storage": str(STORAGE_DIR),
        }
    except RuntimeError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "detail": str(exc),
                "documents": [],
            },
        )


# --------------------------------------------------
# MCP Streamable HTTP
# --------------------------------------------------

# FastMCP's Streamable HTTP ASGI application is mounted here.
# The MCP server and its tools remain in mcp_server/server.py.
mcp_http_app = mcp.streamable_http_app()
app.mount("/mcp", mcp_http_app)


# --------------------------------------------------
# Gradio UI
# --------------------------------------------------

def refresh_documents(query: str):
    try:
        documents = list_documents(query or "")

        if not documents:
            message = (
                f"No files found in {STORAGE_DIR}. "
                "Check the Space bucket mount and folder contents."
            )
        else:
            message = (
                f"Found {len(documents)} file(s) in {STORAGE_DIR}."
            )

        return documents, message

    except Exception as exc:
        return [], f"Document loading failed: {exc}"


with gr.Blocks(title="OhamLab Plugin") as demo:
    gr.Markdown("# OhamLab Plugin")
    gr.Markdown(
        "Documents are loaded from the mounted storage directory. "
        "MCP endpoint: `/mcp/`."
    )

    with gr.Row():
        search_box = gr.Textbox(
            label="Filter documents by path or filename",
            placeholder="Enter a filename or search term",
            scale=4,
        )
        refresh_button = gr.Button("Refresh documents", variant="primary")

    status_box = gr.Textbox(label="Storage status", interactive=False)

    documents_table = gr.Dataframe(
        headers=[
            "name",
            "path",
            "extension",
            "size_bytes",
            "modified_at",
            "searchable_as_text",
        ],
        datatype=[
            "str", "str", "str", "number", "number", "bool"
        ],
        label="Mounted bucket documents",
        interactive=False,
    )

    refresh_button.click(
        fn=refresh_documents,
        inputs=[search_box],
        outputs=[documents_table, status_box],
    )

    search_box.submit(
        fn=refresh_documents,
        inputs=[search_box],
        outputs=[documents_table, status_box],
    )

    demo.load(
        fn=refresh_documents,
        inputs=[search_box],
        outputs=[documents_table, status_box],
    )


app = gr.mount_gradio_app(app, demo, path="/ui")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/ui/")


# --------------------------------------------------
# Local development
# --------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "7860")),
    )

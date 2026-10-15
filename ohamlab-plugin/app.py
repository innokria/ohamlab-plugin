
"""OhamLab Plugin: MCP server, document API, and Gradio UI."""

import hmac
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import gradio as gr
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from mcp_server.server import mcp


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

SPACE_HOST = "rahul7star-ohamlab-plugin.hf.space"

STORAGE_DIR = Path(
    os.getenv(
        "DOCUMENT_STORAGE_DIR",
        "/data/ohamlab-plugin-storage",
    )
).resolve()

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".json",
    ".jsonl",
    ".csv",
    ".xml",
    ".html",
    ".htm",
    ".yaml",
    ".yml",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".css",
    ".sql",
    ".log",
}


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------

def _expected_api_key() -> str:
    """Use the dedicated MCP key, falling back to HF_TOKEN."""
    return (
        os.getenv("OHAM_MCP_API_KEY", "").strip()
        or os.getenv("HF_TOKEN", "").strip()
    )


def _authorized(request: Request) -> bool:
    """Validate the bearer token for protected endpoints."""
    expected = _expected_api_key()

    # Fail closed if no API key is configured.
    if not expected:
        return False

    authorization = request.headers.get("authorization", "")
    scheme, separator, supplied = authorization.partition(" ")

    if not separator or scheme.lower() != "bearer":
        return False

    return hmac.compare_digest(supplied.strip(), expected)


# ---------------------------------------------------------
# MCP lifecycle
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop the MCP session manager with FastAPI."""
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="OhamLab Plugin",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------
# Authentication middleware
# ---------------------------------------------------------

@app.middleware("http")
async def protect_api(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"

    protected = (
        path == "/mcp"
        or path == "/api/documents"
    )

    if protected and not _authorized(request):
        if not _expected_api_key():
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "API authentication is not configured. "
                        "Set OHAM_MCP_API_KEY in Space Secrets."
                    )
                },
            )

        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing bearer token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)


# ---------------------------------------------------------
# Mounted bucket / document storage
# ---------------------------------------------------------

def list_documents(query: str = "", limit: int = 1000) -> list[dict]:
    """
    Read document metadata from the mounted storage directory.

    Files are listed recursively. File contents are not returned
    by this endpoint.
    """
    if not STORAGE_DIR.is_dir():
        raise FileNotFoundError(
            f"Storage directory is unavailable: {STORAGE_DIR}"
        )

    query = query.strip().casefold()
    limit = max(1, min(int(limit), 1000))

    documents = []

    for path in STORAGE_DIR.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue

        try:
            relative_path = path.relative_to(STORAGE_DIR).as_posix()

            # Skip common internal metadata directories.
            if any(
                part in {".git", "__pycache__"}
                for part in Path(relative_path).parts
            ):
                continue

            if query and query not in relative_path.casefold():
                continue

            stat = path.stat()

            documents.append(
                {
                    "path": relative_path,
                    "name": path.name,
                    "extension": path.suffix.lower(),
                    "size_bytes": stat.st_size,
                    "modified_utc": datetime.fromtimestamp(
                        stat.st_mtime,
                        tz=timezone.utc,
                    ).isoformat(),
                    "text_supported": (
                        path.suffix.lower() in TEXT_EXTENSIONS
                    ),
                }
            )

        except (OSError, ValueError):
            # Ignore files that disappear or become unreadable
            # while the mounted directory is being scanned.
            continue

    documents.sort(key=lambda item: item["path"].casefold())

    return documents[:limit]


# ---------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ohamlab-plugin",
        "storage_available": STORAGE_DIR.is_dir(),
    }


# ---------------------------------------------------------
# Document API
# ---------------------------------------------------------

@app.get("/api/documents")
async def documents_api(
    q: str = Query(default="", max_length=500),
    limit: int = Query(default=100, ge=1, le=1000),
):
    try:
        documents = list_documents(q, limit)

        return {
            "ok": True,
            "count": len(documents),
            "documents": documents,
        }

    except FileNotFoundError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": "storage_unavailable",
                "detail": str(exc),
                "documents": [],
            },
        )

    except OSError as exc:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "storage_read_failed",
                "detail": str(exc)[:500],
                "documents": [],
            },
        )


# ---------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------

def refresh_documents(query: str):
    """Return mounted-storage file metadata for the Gradio table."""
    try:
        documents = list_documents(query, limit=1000)

        # Gradio Dataframe expects rows, not dictionaries.
        return [
            [
                item["path"],
                item["size_bytes"],
                item["modified_utc"],
                item["text_supported"],
            ]
            for item in documents
        ]

    except Exception as exc:
        raise gr.Error(f"Unable to read mounted storage: {exc}")


with gr.Blocks(title="OhamLab Plugin") as demo:
    gr.Markdown("# OhamLab Plugin")
    gr.Markdown(
        "Browse files from the mounted bucket storage. "
        "This view displays metadata, not document contents."
    )

    with gr.Row():
        query_box = gr.Textbox(
            label="Filter by file path",
            placeholder="Search filenames or folders...",
            scale=4,
        )
        refresh_button = gr.Button("Refresh", variant="primary")

    document_table = gr.Dataframe(
        headers=[
            "Path",
            "Size (bytes)",
            "Modified (UTC)",
            "Text supported",
        ],
        datatype=["str", "number", "str", "bool"],
        interactive=False,
        wrap=True,
        label="Mounted storage files",
    )

    refresh_button.click(
        fn=refresh_documents,
        inputs=[query_box],
        outputs=[document_table],
    )

    query_box.submit(
        fn=refresh_documents,
        inputs=[query_box],
        outputs=[document_table],
    )

    demo.load(
        fn=refresh_documents,
        inputs=[query_box],
        outputs=[document_table],
    )


# ---------------------------------------------------------
# MCP Streamable HTTP mount
# ---------------------------------------------------------

# The FastMCP server uses streamable_http_path="/".
# Mounting it at "/mcp" exposes its endpoint at /mcp/.
mcp_http_app = mcp.streamable_http_app()
app.mount("/mcp", mcp_http_app)


# ---------------------------------------------------------
# Mount Gradio after registering the API and MCP routes
# ---------------------------------------------------------

app = gr.mount_gradio_app(
    app,
    demo,
    path="/ui",
)


@app.get("/", include_in_schema=False)
async def home():
    return RedirectResponse(url="/ui/")


# ---------------------------------------------------------
# Local development
# ---------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "7860")),
    )

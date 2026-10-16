
"""OhamLab Plugin: MCP server, document API, and Gradio UI."""

import hmac
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import gradio as gr
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from mcp_server.server import mcp


# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("ohamlab.plugin")
auth_logger = logging.getLogger("ohamlab.auth")
request_logger = logging.getLogger("ohamlab.request")


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
    ".txt", ".md", ".markdown", ".rst", ".json", ".jsonl",
    ".csv", ".xml", ".html", ".htm", ".yaml", ".yml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".sql", ".log",
}

PROTECTED_PATHS = {
    "/mcp",
    "/api/documents",
}



# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------

MCP_AUTH_REQUIRED = (
    os.getenv("MCP_AUTH_REQUIRED", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)


def _expected_api_key() -> str:
    """Use the dedicated MCP key, falling back to HF_TOKEN."""
    return (
        os.getenv("OHAM_MCP_API_KEY", "").strip()
        or os.getenv("HF_TOKEN", "").strip()
    )



def _authorized(request: Request) -> bool:
    """Validate a custom OhamLab header or the existing Bearer token."""
    expected = _expected_api_key()

    # Custom plain-text header
    supplied_custom = request.headers.get("x-ohamlab-key", "").strip()

    if expected and supplied_custom:
        if hmac.compare_digest(supplied_custom, expected):
            auth_logger.info(
                "AUTH ALLOWED method=%s path=%s scheme=custom-header",
                request.method,
                request.url.path,
            )
            return True

    # Backward compatibility with Bearer authentication
    authorization = request.headers.get("authorization", "")
    scheme, separator, supplied = authorization.partition(" ")

    if (
        expected
        and separator
        and scheme.lower() == "bearer"
        and supplied.strip()
        and hmac.compare_digest(supplied.strip(), expected)
    ):
        auth_logger.info(
            "AUTH ALLOWED method=%s path=%s scheme=bearer",
            request.method,
            request.url.path,
        )
        return True

    auth_logger.warning(
        "AUTH DENIED method=%s path=%s custom_header_present=%s "
        "authorization_present=%s key_configured=%s",
        request.method,
        request.url.path,
        bool(supplied_custom),
        bool(authorization),
        bool(expected),
    )
    return False



# ---------------------------------------------------------
# MCP lifecycle
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop the MCP session manager with FastAPI."""
    logger.info("Starting OhamLab MCP session manager")

    try:
        async with mcp.session_manager.run():
            logger.info("OhamLab MCP session manager started")
            yield
    finally:
        logger.info("Stopping OhamLab MCP session manager")


app = FastAPI(
    title="OhamLab Plugin",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------
# Request logging and authentication middleware
# ---------------------------------------------------------

@app.middleware("http")
async def protect_api(request: Request, call_next):
    started = time.monotonic()
    path = request.url.path.rstrip("/") or "/"

    host = request.headers.get("host", "")
    client_ip = request.client.host if request.client else "unknown"

    # Forwarded headers are caller-controlled unless a trusted
    # proxy sanitizes them. Log as diagnostics, not trusted identity.
    forwarded_for = request.headers.get("x-forwarded-for", "")
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    user_agent = request.headers.get("user-agent", "")

    request_logger.info(
        "REQUEST START method=%s path=%s query=%r host=%r "
        "client_ip=%s forwarded_for=%r forwarded_proto=%r "
        "user_agent=%r content_type=%r content_length=%r",
        request.method,
        path,
        request.url.query,
        host,
        client_ip,
        forwarded_for,
        forwarded_proto,
        user_agent,
        request.headers.get("content-type", ""),
        request.headers.get("content-length", ""),
    )

    protected = path in PROTECTED_PATHS

    if protected and not _authorized(request):
        key_configured = bool(_expected_api_key())

        if not key_configured:
            response = JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "API authentication is not configured. "
                        "Set OHAM_MCP_API_KEY in Space Secrets."
                    )
                },
            )
        else:
            response = JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing bearer token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        elapsed_ms = round((time.monotonic() - started) * 1000, 2)

        request_logger.warning(
            "REQUEST END method=%s path=%s host=%r client_ip=%s "
            "status=%d auth=denied duration_ms=%.2f",
            request.method,
            path,
            host,
            client_ip,
            response.status_code,
            elapsed_ms,
        )
        return response

    try:
        response = await call_next(request)

        elapsed_ms = round((time.monotonic() - started) * 1000, 2)

        request_logger.info(
            "REQUEST END method=%s path=%s host=%r client_ip=%s "
            "status=%d auth=%s duration_ms=%.2f",
            request.method,
            path,
            host,
            client_ip,
            response.status_code,
            "passed" if protected else "not_required",
            elapsed_ms,
        )

        return response

    except Exception:
        elapsed_ms = round((time.monotonic() - started) * 1000, 2)

        request_logger.exception(
            "REQUEST ERROR method=%s path=%s host=%r client_ip=%s "
            "duration_ms=%.2f",
            request.method,
            path,
            host,
            client_ip,
            elapsed_ms,
        )
        raise


# ---------------------------------------------------------
# Mounted bucket / document storage
# ---------------------------------------------------------

def list_documents(query: str = "", limit: int = 1000) -> list[dict]:
    """List file metadata recursively without returning file contents."""
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
                    "text_supported": path.suffix.lower() in TEXT_EXTENSIONS,
                }
            )

        except (OSError, ValueError):
            logger.debug("Skipping inaccessible file under storage directory")
            continue

    documents.sort(key=lambda item: item["path"].casefold())
    return documents[:limit]


# ---------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------

@app.get("/health")
async def health():
    storage_available = STORAGE_DIR.is_dir()

    logger.info(
        "HEALTH CHECK status=ok storage_available=%s",
        storage_available,
    )

    return {
        "status": "ok",
        "service": "ohamlab-plugin",
        "storage_available": storage_available,
    }


# ---------------------------------------------------------
# Document API
# ---------------------------------------------------------

@app.get("/api/documents")
async def documents_api(
    q: str = Query(default="", max_length=500),
    limit: int = Query(default=100, ge=1, le=1000),
):
    logger.info(
        "DOCUMENT LIST requested query_length=%d limit=%d",
        len(q),
        limit,
    )

    try:
        documents = list_documents(q, limit)

        logger.info(
            "DOCUMENT LIST completed count=%d",
            len(documents),
        )

        return {
            "ok": True,
            "count": len(documents),
            "documents": documents,
        }

    except FileNotFoundError as exc:
        logger.error("DOCUMENT STORAGE unavailable: %s", exc)

        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": "storage_unavailable",
                "detail": str(exc),
                "documents": [],
            },
        )

    except OSError:
        logger.exception("DOCUMENT STORAGE read failed")

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "storage_read_failed",
                "documents": [],
            },
        )


# ---------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------

def refresh_documents(query: str):
    """Return mounted-storage file metadata for the Gradio table."""
    try:
        documents = list_documents(query or "", limit=1000)

        logger.info("GRADIO document refresh count=%d", len(documents))

        return [
            [
                item["path"],
                item["size_bytes"],
                item["modified_utc"],
                item["text_supported"],
            ]
            for item in documents
        ]

    except Exception:
        logger.exception("GRADIO document refresh failed")
        raise gr.Error("Unable to read mounted storage. Check Space logs.")


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

# FastMCP uses streamable_http_path="/".
# Mounting at "/mcp" exposes the endpoint at /mcp/.
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

    logger.info(
        "Starting OhamLab Plugin host=0.0.0.0 port=%s storage=%s",
        os.getenv("PORT", "7860"),
        STORAGE_DIR,
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "7860")),
        log_level=LOG_LEVEL.lower(),
        access_log=True,
    )

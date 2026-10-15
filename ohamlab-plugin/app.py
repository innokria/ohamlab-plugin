
import os
import secrets
from contextlib import asynccontextmanager

import gradio as gr
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from mcp.server.transport_security import TransportSecuritySettings

from mcp_server.server import mcp


# --------------------------------------------------
# Configuration
# --------------------------------------------------

SPACE_HOST = "rahul7star-ohamlab-plugin.hf.space"

transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        SPACE_HOST,
        f"{SPACE_HOST}:443",
    ],
    allowed_origins=[
        f"https://{SPACE_HOST}",
    ],
)


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

    # Require authentication when deployed as an HF Space.
    if not expected:
        return not bool(os.getenv("SPACE_ID"))

    supplied = request.headers.get("authorization", "")
    return secrets.compare_digest(
        supplied,
        f"Bearer {expected}",
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
# Health and document API
# --------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/documents")
async def list_documents(request: Request):
    # Keep your existing document-list implementation here.
    # Example:
    # return your_existing_document_list_function()
    return {"documents": []}


# --------------------------------------------------
# MCP Streamable HTTP transport
# --------------------------------------------------

mcp_http_app = mcp.streamable_http_app()

app.mount("/mcp", mcp_http_app)


# --------------------------------------------------
# Gradio UI
# --------------------------------------------------

# Replace create_ui() with the actual Gradio Blocks/interface
# variable or factory from your existing app.py.
#
# Example:
# demo = gr.Blocks(...)
# app = gr.mount_gradio_app(app, demo, path="/ui")

# IMPORTANT: Mount your existing Gradio UI here.
# Do not create a blank UI if your project already has one.


@app.get("/")
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

# ohamlab-plugin

An independent web-data extraction service intended to connect to DeepSeek Harness (DSH) through the Model Context Protocol (MCP).

## Initial capabilities

- Search the public web using the `ddgs` search library.
- Fetch public pages with Chromium, including many JavaScript-rendered pages.
- Extract readable text and basic page metadata.
- Store documents and task history in JSON files on a mounted Hugging Face Bucket volume.
- Expose search, fetch, search-and-fetch, stored-document retrieval, and task-history MCP tools.
- Provide a Gradio UI for manual testing.

This project implements its own version of a broad search → fetch → extract → store workflow. It is not a copy of TinyFish proprietary technology and does not claim feature parity or guaranteed access to every website.

## Run locally

Python 3.11+ is recommended.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python app.py
```

Open `http://localhost:7860`.

## Hugging Face Space deployment

1. Create a Docker Space and copy/sync this repository into the Space repository.
2. Attach a read-write Hugging Face Bucket volume and mount it at `/data`.
3. Set Space variable `OHAM_DATA_DIR=/data/ohamlab-plugin`.
4. Set Space Secret `OHAM_MCP_API_KEY` to a strong random token.
5. Rebuild the Space and verify `/health` and `/mcp`.

A Bucket is not automatically mounted by this application. Configure the mount in Hugging Face settings; the application writes under `OHAM_DATA_DIR`.

## MCP endpoint

The intended endpoint is:

`https://YOUR-SPACE-NAME.hf.space/mcp`

The MCP server uses Streamable HTTP. Configure DSH to use a remote MCP server and send:

`Authorization: Bearer YOUR_OHAM_MCP_API_KEY`

The exact DSH configuration fields depend on the installed Harness version. Verify that your DSH MCP client supports remote Streamable HTTP and custom headers. Do not expose the endpoint without authentication and do not commit tokens to GitHub.

## MCP tools

- `web_search(query, max_results=5)` — find candidate pages and return URLs/snippets.
- `web_fetch(url, save=true)` — fetch and extract a page, optionally storing it.
- `search_and_fetch(query, max_results=5, fetch_top=3)` — search, fetch the top results, and persist successful extractions.
- `stored_documents(query='', limit=10)` — list saved document metadata.
- `get_document(document_id)` — retrieve the complete saved document.
- `task_history(limit=20)` — inspect recent operations.

## Storage layout

```text
$OHAM_DATA_DIR/
├── documents/<document_id>.json
└── task-history/YYYY-MM-DD.jsonl
```

The document ID is derived from the requested URL. Fetching the same URL updates its saved record. This initial implementation does not yet keep version history for changed content.

## Security and limitations

- Only public HTTP/HTTPS URLs are intended. Basic DNS/IP checks reject obvious private destinations.
- This starter's URL checks are not a complete SSRF boundary: browser subresources, DNS rebinding, and redirect behavior need stronger isolation before accepting arbitrary untrusted URLs.
- Respect website terms, robots policies, rate limits, and applicable law.
- Do not use this service to bypass authentication or access controls.
- Search providers can throttle or change behavior.
- Browser rendering does not guarantee success on every website.
- No autonomous multi-step browser actions, scheduled monitors, or authenticated browser profiles are included in this first milestone.

# OhamLab Plugin — Design and Progress

## Goal

Build an independent MCP-compatible web-data service that DeepSeek Harness can call to search public websites, fetch pages, extract readable content and metadata, and persist results in a Hugging Face Bucket.

The product direction follows the broad public workflow of search → fetch → web agent → browser automation associated with services such as TinyFish. This is an independent implementation, not a copy of proprietary infrastructure and not a claim of feature parity.

## Architecture

DeepSeek Harness → remote MCP Streamable HTTP → web search → browser-rendered fetch → text/metadata extraction → persistent documents and task history → source URLs and document IDs returned to Harness.

- GitHub: source of truth for code.
- Hugging Face Space: runs the application and MCP endpoint.
- Hugging Face Bucket: mounted read-write storage for saved data.

## Phase 1 — Search, Fetch, Store

- [x] Gradio test UI
- [x] MCP Streamable HTTP server
- [x] Search adapter using `ddgs`
- [x] Chromium page rendering using Playwright
- [x] Readable-text and metadata extraction
- [x] JSON document persistence
- [x] JSONL task history
- [x] List and retrieve saved documents
- [x] Docker and startup files
- [x] Basic storage tests
- [ ] Run tests and build the container in the target environment
- [ ] Deploy Space and verify MCP protocol compatibility with the installed DSH version
- [ ] Verify Bucket mount and persistence after restart
- [ ] Verify DSH supports remote MCP headers/authentication

## Phase 2 — Reliability and extraction quality

- [ ] Configurable search providers and retry policies
- [ ] Per-host rate limits
- [ ] Stronger SSRF protections, including browser subresources and DNS rebinding
- [ ] Content hashes and page-version history
- [ ] Structured extraction schemas and integration tests

## Phase 3 — Web agent and browser actions

- [ ] Bounded multi-step task planner
- [ ] Browser interaction tools and trace capture
- [ ] Allowlist/permission controls for state-changing actions
- [ ] Cancellation, timeout and retry controls

## Phase 4 — Monitoring and sessions

- [ ] Website monitor definitions and scheduling
- [ ] Change detection and history
- [ ] Persist only approved non-secret task/session state

## Security and operations

- Never commit tokens or credentials.
- Mount a read-write Bucket and set `OHAM_DATA_DIR` to the mount path; local container disk is ephemeral on hosted Spaces.
- Require authentication for remote MCP access.
- Restrict initial fetching to public URLs and respect website terms and rate limits.
- Current URL validation is a starter safeguard, not a complete boundary for arbitrary hostile URLs.

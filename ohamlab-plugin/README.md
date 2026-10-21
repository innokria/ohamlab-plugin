# OhamLab Agent

**Web search, browser-powered extraction, document storage, and MCP tools — with an optional autonomous LLM research agent.**

OhamLab can run **without any LLM, API key, or external inference server** for manual search, page extraction, and MCP tool serving. Connect an OpenAI-compatible model only when you want OhamLab to decide which tools to call and perform multi-step research autonomously.

> Repository: https://github.com/innokria/ohamlab-plugin  
> Application directory: [`ohamlab-plugin/`](https://github.com/innokria/ohamlab-plugin/tree/main/ohamlab-plugin)

## Features

| Feature | Requires an LLM? | Entry point |
|---|---|---|
| Web UI for manual workflows | No | `ohamlab serve` or `python app.py` |
| Web search | No | `ohamlab search "your query"` *if registered in your local CLI* |
| Fetch and extract a webpage | No | Existing UI/MCP tool; CLI `fetch` requires its own registered wrapper |
| Search → fetch → store | No | Existing MCP workflow |
| MCP server over HTTP | No | `python app.py` → `/mcp` |
| MCP server over stdio | No | `ohamlab mcp-stdio` |
| Autonomous multi-step research | **Yes** | `ohamlab agent "question"` |
| Claude Code / Codex integration | No model **inside OhamLab** | `ohamlab install-claude-code` / `install-codex` |

**Important:** MCP clients such as Claude Code or Codex may use their own LLM. That does not mean the OhamLab MCP service requires a model. The `agent` subcommand is the only mode in this installation layer that explicitly needs an inference provider.

## Architecture

```text
                  User / external coding agent
                             |
          +------------------+------------------+
          |                  |                  |
       Web UI             OhamLab CLI      MCP client/harness
       Gradio         search / agent / serve   Claude / Codex / DSH
          |                  |                  |
          +------------------+------------------+
                             |
                      Existing OhamLab
             search | Chromium | extraction
                      storage | history
                             |
                    Optional LLM runtime
               (only for `ohamlab agent`)
```

The installation layer is intended to sit alongside the original application rather than replace `app.py`, `agent/engine.py`, `browser/automation.py`, or `mcp_server/`.

## Project layout

```text
ohamlab-plugin/                  # GitHub repository root (illustrative)
├── .github/workflows/publish.yml
└── ohamlab-plugin/               # Run local commands from here
    ├── app.py
    ├── ohamlab_cli.py            # CLI entry point
    ├── pyproject.toml            # Python packaging
    ├── requirements.txt
    ├── Dockerfile
    ├── start.sh
    ├── agent/
    ├── browser/
    ├── config/
    ├── mcp_server/
    ├── storage/
    ├── tests/
    └── storage-data/             # Local runtime data; do not commit
```

## 1. Local installation (macOS / Linux)

Requirements: Python 3.11+, Git, and network access for web search and browser installation. The current application uses Playwright/Chromium for some page extraction.

```bash
git clone https://github.com/innokria/ohamlab-plugin.git
cd ohamlab-plugin/ohamlab-plugin

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python -m playwright install chromium

# Confirm CLI registration
ohamlab --help
ohamlab doctor
```

> **Conda users:** You can install into a selected Conda environment instead of creating `.venv`. `ohamlab` is available from any working directory **as long as the environment containing the CLI is active and its executable is on PATH**.

### Windows PowerShell

```powershell
git clone https://github.com/innokria/ohamlab-plugin.git
cd ohamlab-plugin\ohamlab-plugin
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
python -m playwright install chromium
ohamlab --help
```

The original Docker/Hugging Face deployment is separate from the local CLI setup.

## 2. Start locally — no LLM required

From the application directory:

```bash
mkdir -p storage-data
export OHAM_DATA_DIR="$(pwd)/storage-data"
python app.py
```

Or use the `serve` CLI command **if you have added and registered it**:

```bash
ohamlab serve
```

The server normally listens on **http://localhost:7860**. Open that URL for the web UI. The HTTP MCP endpoint is normally **http://localhost:7860/mcp**.

Check health in a second terminal:

```bash
curl -s http://localhost:7860/health
```

Example healthy response:

```json
{"status":"ok","service":"ohamlab-plugin","storage_available":true}
```

`storage_available: false` means the server is running but its configured storage is unavailable. Confirm that `OHAM_DATA_DIR` points to a writable directory **in the environment of the server process**, and restart the server. If the UI says *Server unavailable* despite a healthy `/health` response, inspect the Gradio mount path and routes in `app.py`; HTTP health alone does not prove the UI is correctly mounted.

**Local data:** add `storage-data/` to `.gitignore`. The existing storage implementation stores documents and task history under the configured data directory.

## 3. Search without an LLM

If your CLI includes the `search` command (it was added manually during local setup):

```bash
ohamlab search "find latest AI news"
ohamlab search "Playwright Python documentation" --max-results 10
```

The second command assumes the `--max-results` option from the example CLI wrapper. Check the installed syntax with:

```bash
ohamlab search --help
```

If you see **No such command 'search'**, your installed `ohamlab_cli.py` does not yet register that command. Run `ohamlab --help`, check which file is imported with `python -c "import ohamlab_cli; print(ohamlab_cli.__file__)"`, and ensure your edited CLI is installed in the active environment.

**Fetch:** the original application provides page fetching through its UI/MCP implementation. Do **not** assume `ohamlab fetch` is available until you have added a matching CLI command and verified it appears in `ohamlab --help`.

## 4. Autonomous agent with an LLM provider (optional)

The `agent` command uses an **OpenAI-compatible chat-completions API with tool calling**. Configure a model that supports tool/function calls. It is not required for the web UI, ordinary search, or MCP service.

### NVIDIA API example

```bash
export OHAM_BASE_URL="https://integrate.api.nvidia.com/v1"
export OHAM_MODEL="YOUR_AVAILABLE_TOOL_CALLING_MODEL_ID"
export OHAM_API_KEY="YOUR_API_KEY"

ohamlab agent "Find the official MCP documentation and summarize it with links"
ohamlab agent "Compare Playwright and Selenium using official sources" --json
```

Model identifiers and tool-call support depend on the provider and account. Use a valid model identifier from your provider dashboard rather than assuming a particular model is currently available.

### Other OpenAI-compatible endpoints

```bash
export OHAM_BASE_URL="https://YOUR_PROVIDER/v1"
export OHAM_MODEL="YOUR_TOOL_CALLING_MODEL"
export OHAM_API_KEY="YOUR_API_KEY"

ohamlab agent "Research the latest Python release"
```

The current CLI defaults `OHAM_BASE_URL` to `https://api.openai.com/v1` if unset, and accepts `OPENAI_API_KEY` as a fallback when `OHAM_API_KEY` is not set. For a local OpenAI-compatible server, supply its local `/v1` endpoint; actual support depends on that server's chat-completions and tool-calling implementation. **No model is bundled or downloaded by the installer.**

The agent currently exposes search and fetch tools, uses a bounded tool-call loop, and asks the model to cite source URLs. It is not a guarantee of source accuracy; review consequential research results.

### Security

Do not commit `.env` files or API keys. Use environment variables or a secrets manager. Treat retrieved pages as untrusted input, and restrict untrusted URL fetching from private/internal network addresses before exposing the service publicly.

## 5. MCP server: no LLM required

### Local stdio transport

```bash
ohamlab mcp-stdio
```

This is **not an interactive shell**. The process waits for newline-delimited MCP JSON-RPC messages from an MCP client. Typing an empty line may cause an `Invalid JSON` warning. Use an MCP client or Inspector instead.

```bash
npx @modelcontextprotocol/inspector
```

In Inspector select **STDIO**, command `ohamlab`, argument `mcp-stdio`, then connect and list tools. You can also connect to the running HTTP endpoint using **Streamable HTTP** and `http://localhost:7860/mcp`, supplying authentication if configured.

### Existing MCP tools

| Tool | Purpose |
|---|---|
| `web_search` / `web_search_tool` | Search for relevant pages |
| `web_fetch` | Fetch and extract a page |
| `search_and_fetch` / `search_and_fetch_tool` | Search, fetch, and save selected results |
| `stored_documents` | List saved document metadata |
| `get_document` | Retrieve a stored document |
| `task_history` | Inspect previous operations |

Tool naming can differ between README versions and MCP registrations. **Use MCP Inspector's List Tools response as the source of truth for the running server.**

## 6. Connect to coding agents / harnesses

### Claude Code

Install Claude Code separately, then run:

```bash
ohamlab install-claude-code
claude mcp list
```

This registers the local OhamLab stdio server using the installed `ohamlab` executable. Restart or reconnect Claude Code if needed, and ask it to use OhamLab's web search tool.

### OpenAI Codex CLI

```bash
ohamlab install-codex
codex mcp list
```

This registers OhamLab as a local MCP server. It does not configure a model for OhamLab's separate `agent` command.

### OpenCode

```bash
ohamlab install-opencode
```

The current installer **prints** an MCP configuration snippet. Merge it into your OpenCode configuration; it does not automatically edit the file. Confirm the configuration format against your installed OpenCode version.

### DeepSeek Harness (DSH): remote MCP

Run OhamLab on a remotely reachable HTTPS endpoint first, such as your Hugging Face Space. Then generate a DSH profile fragment:

```bash
ohamlab install-dsh \
  --profile /data/dsh/profiles/web/cordis.patch.yml \
  --url https://YOUR-SPACE.hf.space/mcp
```

The command writes a neighboring file named `ohamlab.cordis.fragment.yml`. **It does not automatically modify `cordis.patch.yml`.** Review and merge the fragment into your DSH profile, configure `OHAM_MCP_API_KEY` for the DSH process, and restart DSH. Check the MCP transport and plugin syntax against your DSH version. The generator refuses to overwrite an existing fragment.

Your remote MCP server should require authentication when publicly reachable. The DSH profile's bearer token must match the secret configured on the remote OhamLab service.

## 7. Hugging Face Spaces / Docker deployment

The existing application can be deployed as a Docker Space using its `Dockerfile` and `start.sh`.

1. Create a Docker Space and deploy the **application directory** contents, including its Dockerfile.
2. Attach a writable persistent storage volume if you need saved documents and task history.
3. Set `OHAM_DATA_DIR` to the mounted storage path (for example `/data/ohamlab-plugin`).
4. Set `OHAM_MCP_API_KEY` as a Space **Secret** if the server uses bearer-token authentication.
5. Start the Space and check `/health`, the UI route, and `/mcp` independently.

Expected remote MCP URL:

```text
https://YOUR-SPACE.hf.space/mcp
```

**Note:** A Hugging Face Bucket or volume is not mounted automatically by the Python application. Configure persistence in the Space settings. Remote availability, timeouts, and browser support depend on the Space configuration.

## 8. Build and distribute

From the application directory:

```bash
python -m pip install --upgrade build
python -m build
ls dist/
```

This builds a Python wheel and source distribution based on `pyproject.toml`. Test the wheel in a clean virtual environment before publishing.

The additive overlay includes a GitHub Actions PyPI publishing workflow. Configure **PyPI Trusted Publishing** and the GitHub Actions environment specified by that workflow before tagging a release. **The existence of a workflow does not mean a package has already been published.**

After the package is actually published to PyPI, users can install it with:

```bash
uv tool install ohamlab-agent
# or
pipx install ohamlab-agent
```

Homebrew and standalone executable installers are **future distribution work**, not part of the current tested release. Avoid advertising `brew install ...` until a formula and release artifacts exist.

## 9. Troubleshooting

| Symptom | What to check |
|---|---|
| `No such command 'search'` | CLI command not registered; check `ohamlab --help` and the imported `ohamlab_cli.py` |
| `No such command 'serve'` | Add/register the `serve` wrapper in the CLI |
| `ohamlab serve` exits nonzero | Look at the **original `app.py` error** above `CalledProcessError`; check whether port 7860 is already occupied |
| Port already in use | `lsof -nP -iTCP:7860 -sTCP:LISTEN` (macOS/Linux) |
| `/health` returns 200 but UI says unavailable | Inspect `gr.mount_gradio_app(...)`, mounted path, frontend requests, and `/config` under the actual mount |
| `storage_available: false` | Set `OHAM_DATA_DIR` to a writable directory **before starting** the server |
| `Invalid JSON: EOF` in `mcp-stdio` | Don't type into stdin; connect through an MCP client/Inspector |
| `agent` fails with missing model | Set `OHAM_MODEL`, `OHAM_BASE_URL`, and `OHAM_API_KEY` |
| Provider rejects tool calls | Select a model/provider that supports OpenAI-style function calling |
| Browser fetch fails | Install Chromium with `python -m playwright install chromium` |

Useful checks:

```bash
ohamlab --help
ohamlab doctor
which ohamlab
python -c "import ohamlab_cli; print(ohamlab_cli.__file__)"
curl -i http://localhost:7860/health
```

## Development principles

- Preserve existing OhamLab web-search, browser, storage, and MCP logic.
- Keep model inference optional; manual workflows must remain usable without an API key.
- Add new capabilities through small CLI wrappers and integrations.
- Prefer stdio MCP for local harnesses and authenticated Streamable HTTP for remote clients.
- Keep secrets and persistent data out of Git.
- Validate installer changes against the actual CLI and harness versions.

## License and contributions

See the repository for its current license and contribution terms. Before publishing to PyPI, confirm package-name availability, licensing, and release credentials.

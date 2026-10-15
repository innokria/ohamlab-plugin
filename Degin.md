# OhamLab Plugin


```
GitHub: ohamlab-plugin
        |
        | Pull code during build/startup
        v
 Space
        |
        +-- MCP server
        +-- Web-agent engine
        +-- Browser automation
        |
        +-- Bucket
              |
              +-- Saved sessions (if securely supported)
              +-- Monitor configurations
              +-- Task history
              +-- Persistent data
```
## Harness
```
 Harness
       |
       | MCP
       v
ohamlab-plugin (Space)
       |
       +-- Web search
       +-- Web fetch
       +-- Browser automation
       +-- Autonomous task execution
       +-- Saved sessions
       +-- Website monitoring
```


## First atempt

```
 Harness
Ask: find a website and collect its data

MCP tools in ohamlab-plugin
Search → Fetch → Extract → Store → Retrieve

Website data store
URL · page title · extracted text · metadata · timestamps · task history

Structured results returned to Harness, with source URLs for traceability.
```
## 1. Objective

Build a modular, MCP-compatible agent service

## 2. Architecture

- GitHub: `ohamlab-plugin`
- Runtime: Hugging Face Docker Space
- UI: Gradio
- Tool interface: Model Context Protocol (MCP)
- Agent execution: Modular web-agent engine
- Browser interaction: Dedicated browser automation module
- Persistence: Hugging Face Bucket

## 3. Development Phases

### Phase 1 — MCP Search Demo
- [ ] Create repository structure.
- [ ] Build Gradio search interface.
- [ ] Implement a search tool.
- [ ] Expose the search tool through an MCP server.
- [ ] Test search execution and error handling.
- [ ] Add automated tests.

**Acceptance criteria:** A user can submit a query, execute the search tool, and inspect the results.

### Phase 2 — Hugging Face Deployment
- [ ] Create Docker Space.
- [ ] Pull the configured GitHub revision.
- [ ] Install dependencies at build time where possible.
- [ ] Configure startup and health checks.
- [ ] Configure secrets securely.
- [ ] Verify the deployed search demo.

**Acceptance criteria:** The Space starts reliably and executes searches without requiring manual code changes.

### Phase 3 — Persistent Storage
- [ ] Configure the Hugging Face Bucket.
- [ ] Verify supported file operations.
- [ ] Store application configuration.
- [ ] Store task history.
- [ ] Define retention and cleanup policies.
- [ ] Evaluate secure session persistence.

**Acceptance criteria:** Required application data survives Space restarts.

### Phase 4 — Web-Agent Engine
- [ ] Define the task execution interface.
- [ ] Connect the agent to MCP tools.
- [ ] Add execution limits and timeouts.
- [ ] Record task status and errors.
- [ ] Add cancellation and failure handling.

**Acceptance criteria:** The agent can execute a bounded task using the search tool.

### Phase 5 — Browser Automation
- [ ] Select a browser automation implementation.
- [ ] Verify browser dependencies work in the Space.
- [ ] Add navigation and page inspection.
- [ ] Add controlled interaction with web pages.
- [ ] Define permissions and safety limits.

**Acceptance criteria:** A bounded browser task can execute and return its results.

### Phase 6 — Monitoring
- [ ] Add monitor configuration.
- [ ] Add scheduled execution where supported.
- [ ] Persist task outcomes.
- [ ] Add execution status and error reporting.
- [ ] Define resource and execution limits.

**Acceptance criteria:** Configured monitoring tasks can run and record their outcomes.

## 4. Engineering Rules

- Keep source code in GitHub.
- Keep runtime configuration separate from source code.
- Never commit secrets.
- Do not assume that Bucket storage supports POSIX filesystem operations.
- Do not depend on hard links for persistent storage.
- Keep browser automation separate from MCP tool definitions.
- Add tests before expanding the agent's capabilities.
- Use bounded execution, timeouts, and explicit permissions.
- Record implementation decisions and test results in this document.

## 5. Current Status

**Current phase:** Phase 1 — MCP Search Demo

**Next milestone:** Create the repository files and get one search tool working end to end.

**Deferred:** Autonomous agent loops, browser automation, scheduled monitoring, and session restoration.

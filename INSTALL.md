# OhamLab additive install layer

Copy the contents of this overlay to the matching paths in the root of https://github.com/innokria/ohamlab-plugin . The existing app.py, Dockerfile, agent/engine.py, MCP server and other original modules remain unchanged.

## Local test (run from ohamlab-plugin/)

python -m pip install -e .
ohamlab doctor
ohamlab install-agent
ohamlab mcp-stdio  # stdio server; stop with Ctrl+C

## Agent mode

export OHAM_BASE_URL=https://integrate.api.nvidia.com/v1
export OHAM_API_KEY=YOUR_KEY
export OHAM_MODEL=YOUR_TOOL_CAPABLE_MODEL
ohamlab agent 'Find official documentation for MCP' --json

## Integrations

ohamlab install-claude-code
ohamlab install-codex
ohamlab install-opencode   # prints a config to merge

ohamlab install-dsh --profile /data/dsh/profiles/web/cordis.patch.yml --url https://YOUR-SPACE.hf.space/mcp

## Publishing

Configure a PyPI Trusted Publisher for this repository and GitHub Actions environment `pypi`, then tag v0.1.0. The workflow builds and publishes a Python wheel and sdist. After PyPI publishing, users can run `uv tool install ohamlab-agent` or `pipx install ohamlab-agent`.

## Important limitations

- This overlay was not integration-tested against the live GitHub checkout (network cloning unavailable).
- The existing server has a hardcoded HF Space host and may need separate local transport-security configuration for remote deployment.
- DSH installation currently generates a fragment rather than automatically patching a version-dependent config file.
- OpenCode integration generates a config snippet rather than changing the user's config.
- Homebrew and standalone binaries are not built by this workflow. They require release artifacts and a separate formula/tap.
- Web fetching needs SSRF/network egress hardening before use with untrusted users.
- No model is bundled; an API model with tool-calling support is required.

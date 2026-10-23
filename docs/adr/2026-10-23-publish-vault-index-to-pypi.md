---
status: accepted
date: 2026-10-23
entities: [vault-index-server, claude-second-brain]
---

# ADR: Publish vault-index to PyPI from the in-place server.py

## Context
The search server is useful on its own, without the rest of claude-second-brain. A PyPI package makes it one line to add (`uvx vault-index`) and lets it be listed in the MCP registry. Hooks, tests, invariants and the eval all import or run `mcp/server.py` by path, so a package layout would touch every one of them.

## Decision
- Keep `mcp/server.py` where it is. Hatchling ships it in the wheel as the module `vault_index` (`force-include`), with the console script `vault-index = vault_index:main`.
- `[tool.uv] package = false`, so `uv run --project mcp` keeps running the source file, not an installed copy.
- Distribution name `vault-index`; registry name `io.github.GitGudatCodeing/vault-index` (the README carries the `mcp-name` line that proves ownership).
- Release on a `v*` tag: `.github/workflows/release.yml` checks the tag matches `pyproject.toml` and `server.json`, publishes to PyPI with trusted publishing (no token), then publishes `server.json` with `mcp-publisher` (pinned v1.8.1, checksum verified, GitHub OIDC login).
- Quickstart uses `uvx --python 3.12`: without it uvx picked Python 3.15, where onnxruntime has no wheels.

## Options considered
- A real package (`mcp/vault_index/`): cleaner wheel, but every path in hooks, tests and invariants changes. No gain for users.
- Top-level module `server`: would clash with anything else named `server` in the environment.
- API token in a repo secret: works, but a long-lived secret; trusted publishing needs none.

## Consequences
- The user creates the PyPI account and the pending trusted publisher (repo claude-second-brain, workflow `release.yml`, environment `pypi`) once.
- Versions live in two files (`mcp/pyproject.toml`, `server.json`); the release job fails if they differ from the tag.
- The PyPI README (`mcp/README.md`) has no eval numbers, so a published release never shows stale scores.

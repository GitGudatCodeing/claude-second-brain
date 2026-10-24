# Contributing

Issues and pull requests are welcome. Keep changes small and measured.

This repo is generated from the maintainer's own vault by an export script. Merged pull requests are ported back there before the next export, so a merge may be followed by a commit that restates it.

## Before a pull request
```bash
uv sync --project mcp
uv run --project mcp --with pytest pytest tests -q
uvx ruff check .
VAULT_INDEX_DB=/tmp/csb-eval.db uv run --project mcp python eval/run_eval.py --modes all
python scripts/invariants.py
```

## Rules
- **Search changes need numbers.** Run the eval before and after. Keep a change only if it beats `eval/baseline.json`; put the before and after table in the pull request. Failed experiments are worth a pull request too, as a lesson or an ADR update.
- **Do not edit golden labels to raise a score.** Change labels only when they are wrong, and say why.
- **Keep the server and the invariants in sync.** `invariants.py` mirrors the server's extension list, skip list and ignore rules on purpose (standard library only, no model load). The tests check that they agree.
- **New check, prove it fails.** A new invariant or test should be seen failing once before it is trusted.
- **Lessons go through `scripts/learn.py`**, never by hand: lesson, cause, how to detect it.
- **No real personal data** in `example-vault/`, tests or issues. Everything there is fictional.
- **No new dependencies or hooks without a measured need.** Hooks must never block a session: catch errors and exit 0.

## Releasing
Set the same version in `mcp/pyproject.toml` and `server.json`, add it to `CHANGELOG.md`, then push a tag `vX.Y.Z`. The release workflow publishes `vault-index` to PyPI (trusted publishing) and then to the MCP registry.

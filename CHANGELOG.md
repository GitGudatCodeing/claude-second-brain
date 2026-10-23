# Changelog

## Unreleased
- `scripts/setup.py`: one-command setup (writes `.mcp.json`, indexes, runs the invariants). CI runs it on every push.
- Context guard: silent until the hard limit, then requires a handoff note and a session card. `handoff.json` holds only `hard_tokens`.
- `CLAUDE.md` explains `example-vault/` so Claude does not mistake sample data for your own notes.
- `run_eval.py --modes all` adds a naive grep baseline (no index): 0.426 NDCG@5 against 0.782 for hybrid on the sample vault.
- CI actions bumped (checkout v7, cache v6, setup-uv v10.2.0).

## 0.1.0 (2026-10-23)
First public release: vault-index MCP server (FTS5 + sqlite-vec, keyword weight 0.1 in fusion), re-index, context guard and pre-compaction hooks, invariants, `/recall` `/adr` `/learn` `/ingest` `/handoff`, sample vault with a 32-question eval, 29 tests, CI on Ubuntu and Windows.

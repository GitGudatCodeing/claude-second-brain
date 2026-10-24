# Changelog

## Unreleased
- README: `uvx vault-index` quickstart and PyPI badge.

## 0.2.0 (2026-10-24)
- `vault-index` is packaged for PyPI (`uvx vault-index`) and described in `server.json` for the MCP registry. A tag push publishes both (`.github/workflows/release.yml`, trusted publishing, no tokens).
- `path_prefix` searches rank only chunks under the prefix (they no longer come back short when other folders fill the candidate pool), and accept paths relative to a source and either slash.
- Indexing embeds before it touches the index and rolls back on errors, so a failed embedding can no longer leave a file marked indexed with no chunks.
- A file that grows past 1 MB or stops being valid UTF-8 is dropped from the index instead of serving its old text.
- `remove_source` and `list_sources` match paths exactly (`_` and `%` in folder names were LIKE wildcards).
- The re-index hook works for vaults inside a folder named like a skip dir (`build`, `dist`, `bin`).
- `learn.py --supersede` with the text of an existing lesson now changes nothing and says so.
- Eval: 12 harder paraphrase questions (44 in total). `eval/compare_basic_memory.py` compares retrieval with basic-memory.
- LICENSE holder: GitGudatCodeing. 7 new regression tests (38 in total).
- `scripts/setup.py`: one-command setup (writes `.mcp.json`, indexes, runs the invariants). CI runs it on every push.
- Context guard: silent until the hard limit, then requires a handoff note and a session card. `handoff.json` holds only `hard_tokens`.
- `CLAUDE.md` explains `example-vault/` so Claude does not mistake sample data for your own notes.
- `run_eval.py --modes all` adds a naive grep baseline (no index): 0.426 NDCG@5 against 0.782 for hybrid on the sample vault.
- CI actions bumped (checkout v7, cache v6, setup-uv v10.2.0).

## 0.1.0 (2026-10-23)
First public release: vault-index MCP server (FTS5 + sqlite-vec, keyword weight 0.1 in fusion), re-index, context guard and pre-compaction hooks, invariants, `/recall` `/adr` `/learn` `/ingest` `/handoff`, sample vault with a 32-question eval, 29 tests, CI on Ubuntu and Windows.

# claude-second-brain

A local, private memory system for Claude Code: markdown notes as the record, hybrid search over them through an MCP server, decision records and lessons as first-class files, and hooks that keep it all in sync.

> Status: early. A sample vault, tests, CI and a full README with eval results are coming.

## What it does
- **Hybrid search** (`mcp/server.py`): SQLite FTS5 keywords plus sqlite-vec embeddings (fastembed, CPU), merged with reciprocal rank fusion. One file, offline.
- **Auto re-index**: a PostToolUse hook re-indexes every file Claude writes or edits.
- **Decisions and lessons**: `/adr` writes decision records, `/learn` writes lessons as testable directives.
- **Knowledge graph**: entities and relations via the MCP memory server, each fact pointing at its source file.
- **Session handoffs**: a context guard warns at a soft token limit and requires `/handoff` at a hard one.
- **Invariants**: `scripts/invariants.py` checks at session start that every pipeline reaches its consumer.
- **Retrieval eval**: `eval/run_eval.py` scores NDCG@5, MRR and Recall@5 against a golden set; search changes are kept only if they beat the baseline.

## Quickstart
Needs Python 3.10 to 3.13, [uv](https://docs.astral.sh/uv/), Node.js (for the memory server) and Claude Code.

```bash
git clone <this repo> && cd claude-second-brain
uv sync --project mcp
cp .mcp.json.example .mcp.json   # then set MEMORY_FILE_PATH to an absolute path
claude
```

In the first session, ask Claude to run `index_paths` with this folder's absolute path, then try `/recall`.

## Design decisions
See `docs/adr/`, including the search experiments that did not work.

## License
MIT

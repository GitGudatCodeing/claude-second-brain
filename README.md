# claude-second-brain

[![CI](https://github.com/GitGudatCodeing/claude-second-brain/actions/workflows/ci.yml/badge.svg)](https://github.com/GitGudatCodeing/claude-second-brain/actions/workflows/ci.yml)

A local, private memory system for Claude Code: markdown notes as the record, hybrid search over them through an MCP server, decision records and lessons as first-class files, and hooks that keep it all in sync.

> Status: early. A demo is coming.

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

## Sample vault and eval
`example-vault/` is a fictional person's notes, decisions and lessons (two side projects, running, home network). `eval/golden.jsonl` asks 32 questions about it and about this repo's own docs, worded differently from the notes on purpose.

```bash
VAULT_INDEX_DB=/tmp/csb-eval.db uv run --project mcp python eval/run_eval.py --modes all
```

| Mode | NDCG@5 | MRR | Recall@5 |
|---|---|---|---|
| hybrid (served) | 0.720 | 0.755 | 0.807 |
| keyword only (FTS5) | 0.583 | 0.646 | 0.672 |
| vector only | 0.773 | 0.797 | 0.865 |

Vector-only beats hybrid on this corpus: keyword matches add noise for paraphrased questions. Tuning the fusion is the next experiment, kept only if it beats `eval/baseline.json`.

Your own notes go in `notes/`; delete `example-vault/` if you do not need the eval.

## Tests and CI
```bash
uv run --project mcp --with pytest pytest tests -q
uvx ruff check .
```

The tests use a fake bag-of-words embedder, so they run in about a second without downloading a model. CI runs lint, tests, the retrieval eval and the invariants on Ubuntu and Windows for every push.

## Design decisions
See `docs/adr/`, including the search experiments that did not work.

## License
MIT

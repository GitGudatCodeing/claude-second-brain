# vault-index

<!-- mcp-name: io.github.GitGudatCodeing/vault-index -->

Local hybrid search for markdown vaults and codebases, served as an MCP server. Keyword search (SQLite FTS5) and vector search (sqlite-vec, `bge-small-en-v1.5` on CPU) are merged with reciprocal rank fusion. Everything lives in one SQLite file on your machine; no cloud services.

Part of [claude-second-brain](https://github.com/GitGudatCodeing/claude-second-brain), where every search change is measured against golden question sets and compared with naive grep and basic-memory (see its README for the numbers).

## Use with Claude Code

```bash
claude mcp add vault-index -- uvx --python 3.12 vault-index
```

Then ask Claude to index a folder, for example: "index_paths ~/notes". After that, `search_notes` finds paraphrased answers with file path and heading. The first run downloads the embedding model (about 65 MB).

## Tools
- `index_paths(paths, reindex=False)`: add folders or files as sources and sync them. With no paths, re-syncs every source (new, changed and deleted files).
- `search_notes(query, limit=8, path_prefix=None)`: hybrid search; returns chunks with file path and heading path.
- `get_note(path)`: full text of an indexed file.
- `list_sources()`, `remove_source(path)`.

Markdown is chunked by heading. A `.indexignore` in a source folder lists relative paths to skip.

## Settings
| Env var | Default |
|---|---|
| `VAULT_INDEX_DB` | `~/.mcp-memory/vault-index.db` |
| `VAULT_MODEL_CACHE` | `~/.mcp-memory/models` |

Python 3.10 to 3.13 (`--python 3.12` keeps uvx off newer Pythons that onnxruntime does not support yet). MIT license.

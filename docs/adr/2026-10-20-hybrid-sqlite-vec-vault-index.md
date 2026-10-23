---
status: accepted
date: 2026-10-20
entities: [second-brain-architecture, vault-index-server, memory-server]
---

# ADR: Hybrid sqlite-vec + FTS5 vault index with fastembed

## Context
The knowledge graph (`memory-server`) stores distilled facts but not raw note or code text. We need local, private semantic search over markdown vaults and codebases on Windows (Python 3.12 + uv, no GPU requirement, no cloud services).

## Decision
Build a small custom Python MCP server (`vault-index-server`) that stores chunks in one SQLite file, combining FTS5 keyword search and sqlite-vec vector search via reciprocal rank fusion, with embeddings from fastembed (BAAI/bge-small-en-v1.5, CPU/ONNX).

## Options considered
- Custom sqlite-vec + FTS5 server: full control over chunking, incremental indexing and tools; we maintain about 250 lines of code.
- basic-memory: markdown-native and quick to try, but overlaps with the existing knowledge graph.
- mcp-server-qdrant: easy setup, but a snippet store rather than a vault/codebase indexer.
- Ripgrep plus filesystem MCP: cheapest, but no semantic search.

## Consequences
- Search works offline; the index is one portable file (`~/.mcp-memory/vault-index.db`).
- Indexing is explicit, mitigated by the PostToolUse re-index hook; deletions need `index_paths` with no arguments.
- Pinned `mcp<2` because mcp 2.x renamed FastMCP.

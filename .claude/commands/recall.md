---
description: Unified recall - notes and lessons (the record) plus the graph's entity map, with a sourced summary
argument-hint: <topic>
allowed-tools: Read, mcp__memory__search_nodes, mcp__memory__open_nodes, mcp__vault-index__search_notes, mcp__vault-index__get_note
---

Recall everything known about: **$ARGUMENTS**

If the topic is empty, ask for one and stop. This command is read-only: do not write to the graph, the index or any file.

## 1. Notes (the record)
- `search_notes` with the topic (limit 8). Also run it with `path_prefix` `<SecondBrain root>/docs/lessons.md` to surface relevant lessons.
- Use `get_note` only when a chunk is clearly relevant and needs fuller context.
- If results look stale or empty, mention that `index_paths` (or `/ingest <path>`) may be needed.

## 2. Graph (the map)
- `search_nodes` with the topic and one or two key-term variants; `open_nodes` on the best matches for their relations.
- Use it to find related topics; if it names a source file that the notes search missed, run one more `search_notes` for it.

## 3. Synthesize
Reply in this shape, concisely:

**Summary**: 2-5 sentences. Where the graph and a file disagree, trust the file and flag the graph entry as needing a fix.

**From notes and code**: the best chunks as bullets, each with a clickable source like `[CLAUDE.md](<SecondBrain root>/CLAUDE.md)` plus the heading.

**Lessons**: active lessons that apply, with their ids. Ignore superseded or retired ones.

**Related (graph)**: related entities and relations, one line each.

**Gaps**: what was not found, and a suggested follow-up (`/ingest`, `/adr`, `/learn`).

Cite only what the tools returned; never fill gaps from guesses.

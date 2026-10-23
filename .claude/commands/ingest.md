---
description: Index a file or folder into the vault index and distill its key concepts into the Knowledge Graph
argument-hint: <file-or-folder path>
allowed-tools: Read, Glob, mcp__vault-index__index_paths, mcp__vault-index__search_notes, mcp__vault-index__get_note, mcp__vault-index__list_sources, mcp__memory__search_nodes, mcp__memory__create_entities, mcp__memory__add_observations, mcp__memory__create_relations
---

Ingest: **$ARGUMENTS**

If the path is empty, ask for one and stop.

## 1. Index
- Resolve the path to an absolute path and confirm it exists (Glob/Read). Stop with a clear message if it does not.
- Call `index_paths` with that path (it is remembered as a source), then `list_sources` and report files and chunks added.

## 2. Distill
- Read the ingested content. For a folder, read the most informative files first (README, index or overview notes, ADRs, `CLAUDE.md`); `search_notes` with `path_prefix` set to the folder helps find the rest. Cap it at roughly 15 files; say what you skipped.
- The files stay the record; the graph only gets a map of them. Extract only durable entities:
  - named projects, systems, tools and technologies
  - people and organisations that recur
  - user preferences and conventions (one fact each)
- Skip trivia, temporary details, lessons (those go to `/learn`) and anything resembling a secret, key or token. Fewer, better entities beat many weak ones; aim for at most about 10 per ingest.

## 3. Update the Knowledge Graph
- Run `search_nodes` for each candidate entity first. If it exists, `add_observations` (skip observations already recorded); otherwise `create_entities` using normalized kebab-case names.
- Each observation: one short atomic fact ending in `source: <file path>`. Never copy passages.
- `create_relations` with directed active-voice types (`uses`, `depends_on`, `documents`, `decided_in`).

## 4. Report
List the entities created or updated, the relations added, and the files read. Mention anything skipped.

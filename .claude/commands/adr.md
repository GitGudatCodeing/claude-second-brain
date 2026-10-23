---
description: Create an Architecture Decision Record in docs/adr/ and save the distilled decision to the Knowledge Graph
argument-hint: <decision title>
allowed-tools: Read, Write, Glob, mcp__memory__search_nodes, mcp__memory__create_entities, mcp__memory__add_observations, mcp__memory__create_relations, mcp__vault-index__search_notes
---

Create an ADR for: **$ARGUMENTS**

If the title is empty, ask for one and stop.

## 1. Gather context
- Use the current conversation as the main source for context, options and rationale. Do not invent facts; if something essential is missing, ask one concise question first.
- `search_nodes` on the title's key terms to find existing entities to link to, and `search_notes` for related notes or earlier ADRs (`path_prefix` `<SecondBrain root>/docs/adr`).

## 2. Write the file
- Path: `<SecondBrain root>/docs/adr/YYYY-MM-DD-<kebab-title>.md` using today's date. Use Glob first; never overwrite an existing file (append `-2` if needed).
- Use the Write tool (the PostToolUse hook then re-indexes the note automatically). Template:

```markdown
---
status: proposed | accepted | superseded | rejected
date: YYYY-MM-DD
entities: [entity-name, ...]
supersedes: <earlier ADR filename, optional>
---

# ADR: <Title>

## Context
<Forces and constraints that led to this decision.>

## Decision
<One or two sentences: what we decided.>

## Options considered
- <Option A>: <pros / cons>
- <Option B>: <pros / cons>

## Consequences
- <What gets easier, what gets harder, follow-ups.>
```

Pick the status honestly (`accepted` only if the user has clearly decided).

## 3. Save to the Knowledge Graph
- Create an entity named `adr-YYYY-MM-DD-<kebab-title>` (type `decision`) with observations: the decision in one sentence, the status, the key reason, and `source: <ADR file path>`.
- `create_relations` from the ADR entity to each linked entity (e.g. `affects`, `uses`, `supersedes`). Reuse existing entity names found in step 1; only create new entities when truly needed. For a superseded ADR, add an observation `superseded by <new ADR>` to its entity.
- Never put secrets in the file or graph; keep graph observations short.

## 4. Report
Give the file path, status, and the entities and relations written.

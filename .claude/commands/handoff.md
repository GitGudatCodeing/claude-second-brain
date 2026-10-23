---
description: Write a handoff note to docs/handoffs/ and continue the work in a fresh session
argument-hint: [topic, optional]
allowed-tools: Read, Write, Glob, Grep, ToolSearch, mcp__vault-index__search_notes, mcp__vault-index__index_paths, mcp__ccd_session__start_session
---

Hand off the current work: **$ARGUMENTS** (if empty, name the topic from the conversation).

Global command (user-level). Notes from every project go to the SecondBrain, so `/recall` finds them.

## 1. Gather
- Source: this conversation. Do not invent; mark anything unsure as an open question.
- Decisions and lessons already recorded: check this project's ADRs and lessons if it has them (SecondBrain: `docs/adr/`, `docs/lessons.md`).
- If a decision or lesson is not recorded yet, list it under "Not yet recorded" so the next session can run `/adr` or `/learn`. Do not write those now.

## 2. Write the note
- Path: `<SecondBrain root>/docs/handoffs/YYYY-MM-DD-<kebab-topic>.md` (today's date). Glob first; never overwrite (append `-2`).
- Use the Write tool. Under ~800 words. No secrets, keys or tokens.
- Outside the SecondBrain folder the re-index hook does not run: call `index_paths` with the note's path (load it with ToolSearch if needed). If the tool is unavailable, skip it; the SecondBrain invariants flag the note next session.

```markdown
---
date: YYYY-MM-DD
status: open
topic: <topic>
project: <absolute path of the working directory>
---

# Handoff: <topic>

## Goal
<What the user wants, in their words where possible.>

## Done
- <Finished items, with file paths.>

## Current state
<Where things stand right now: what works, what is half-done, what was being tried.>

## Next steps
1. <First concrete action.>

## Key files
- `<path>`: <why it matters>

## Watch out
- <Gotchas, lesson ids (L-xxxx), user preferences that apply.>

## Open questions
- <Waiting on the user, or unresolved.>

## Not yet recorded
- <Decisions for /adr, lessons for /learn. Or "none".>
```

## 3. Start the new session
- Load the tool: ToolSearch `select:mcp__ccd_session__start_session`.
- Call it with `context: "fresh"`, a short `title`, and this brief (it starts in the same project folder):
  "Continue from the handoff note `<path>`. Read it first (get_note or Read), change its `status: open` to `status: picked-up`, then work on Next steps. Ask the user before acting on Open questions."
- `initiation`: `"user_asked"` when the user typed `/handoff` or asked for a new session; `"own_initiative"` (a card the user clicks) when the context guard triggered this.
- If the tool is not available (plain CLI), give the user this to run in the project folder instead: `claude "Read <absolute note path> and continue from Next steps"`.

## 4. Report
The note's path and a link to the new session (or the card). Say this session can be archived once the new one is running.

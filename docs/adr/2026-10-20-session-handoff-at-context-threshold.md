---
status: accepted
date: 2026-10-20
entities: [second-brain-architecture]
---

# ADR: Session handoff at a context threshold

## Context
One session ran all day across unrelated tasks and reached 732k tokens before auto-compaction. Every turn re-sends the whole context, so long sessions are expensive and drift. Claude Code has no context-threshold hook event, but every assistant entry in the transcript records `usage`, so input + cache read + cache write gives the real context size. Existing community handoff skills (for example `392fyc/claude-handoff`) are manual only and launch a terminal, which does not fit the desktop app.

## Decision
Build our own: a UserPromptSubmit hook (`scripts/context_guard.py`) reads the transcript's latest usage and warns once at the soft limit and requires `/handoff` at the hard limit (`.claude/handoff.json`: 300k / 450k). `/handoff` writes `docs/handoffs/YYYY-MM-DD-<topic>.md` (indexed) and starts a fresh desktop session with the note as its brief. A PreCompact hook writes a mechanical fallback snapshot to `docs/handoffs/auto/` (not indexed).

## Options considered
- Install `claude-handoff`: good note structure (borrowed), but no automatic trigger and a terminal-based launch.
- Regular `/compact`: keeps one session alive but loses detail silently; handoff notes are explicit and searchable.
- Thresholds 450k / 600k (user's first idea): workable on a 1M window, but turns cost about 5x more at 450k than at 80k; 300k / 450k chosen, one line to change.
- Status line: sees context size but cannot inject instructions.

## Consequences
- The guard checks only when the user sends a message; a long autonomous run can pass the hard limit before it fires. Add a Stop hook check if that happens in practice.
- Starting the new session without a click needs the user's request in that turn; when the guard triggers it, the new session appears as a card to click.
- Made global (same day): `/handoff` lives in `~/.claude/commands/`, and the two hooks belong in `~/.claude/settings.json` so every project uses them. Notes from any project land in SecondBrain `docs/handoffs/` with a `project:` field. The user adds the user-level hooks by hand (Claude is not allowed to edit its own user settings); until then they run from the SecondBrain project settings.
- Invariant `handoff` checks the hooks (at either level, flagging duplicates), thresholds, the global command and the `auto/` index exclusion.

## Update (2026-10-23): hard limit only
The soft notice was dropped at the user's request: a reminder at 300k interrupted work and added nothing. The guard is now silent until the hard limit (450k), then requires the handoff note and a session card. `handoff.json` holds only `hard_tokens`.

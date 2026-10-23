---
description: Record a lesson as a dated directive in docs/lessons.md (after a correction, failed approach or false assumption)
argument-hint: <what went wrong or what to remember>
allowed-tools: Bash(python scripts/learn.py:*), mcp__vault-index__search_notes
---

Record a lesson about: **$ARGUMENTS** (if empty, use the most recent correction or failure in this conversation).

1. `search_notes` with `path_prefix` `<SecondBrain root>/docs/lessons.md` to check for an existing lesson on this. If one exists and is wrong or outdated, supersede it instead of adding a duplicate.
2. Phrase the lesson as an instruction to your future self, specific and testable.
   - Good: "Write Windows paths in hook commands with forward slashes; Git Bash strips backslashes."
   - Bad: "The hook broke because of paths."
3. Run from `<SecondBrain root>`:
   - New: `python scripts/learn.py "<lesson>" --cause "<root cause>" --detect "<how to notice it next time>" --tags a,b`
   - Replace: `python scripts/learn.py --supersede L-000N "<new lesson>" --cause ... --detect ... --tags ...`
   - Retire (no longer true): `python scripts/learn.py --retire L-000N --reason "<why>"`
4. If nothing durable was learned, say so and record nothing. Never record secrets, and never record narration ("I tried X").
5. Report the id and the lesson in one line.

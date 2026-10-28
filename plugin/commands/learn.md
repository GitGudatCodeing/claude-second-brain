---
description: Record a lesson as a dated directive in docs/lessons.md (after a correction, failed approach or false assumption)
argument-hint: <what went wrong or what to remember>
allowed-tools: Bash(uv run --no-project --python 3.12 python *learn.py*), mcp__plugin_second-brain_vault-index__search_notes
---

Record a lesson about: **$ARGUMENTS** (if empty, use the most recent correction or failure in this conversation).

1. `search_notes` with `path_prefix` `${CLAUDE_PROJECT_DIR}/docs/lessons.md` to check for an existing lesson on this. If one exists and is wrong or outdated, supersede it instead of adding a duplicate.
2. Phrase the lesson as an instruction to your future self, specific and testable.
   - Good: "Write Windows paths in hook commands with forward slashes; Git Bash strips backslashes."
   - Bad: "The hook broke because of paths."
3. Run:
   - New: `uv run --no-project --python 3.12 python "${CLAUDE_PLUGIN_ROOT}/scripts/learn.py" --root "${CLAUDE_PROJECT_DIR}" "<lesson>" --cause "<root cause>" --detect "<how to notice it next time>" --tags a,b`
   - Replace: `uv run --no-project --python 3.12 python "${CLAUDE_PLUGIN_ROOT}/scripts/learn.py" --root "${CLAUDE_PROJECT_DIR}" --supersede L-000N "<new lesson>" --cause ... --detect ... --tags ...`
   - Retire (no longer true): `uv run --no-project --python 3.12 python "${CLAUDE_PLUGIN_ROOT}/scripts/learn.py" --root "${CLAUDE_PROJECT_DIR}" --retire L-000N --reason "<why>"`
4. If nothing durable was learned, say so and record nothing. Never record secrets, and never record narration ("I tried X").
5. Report the id and the lesson in one line.

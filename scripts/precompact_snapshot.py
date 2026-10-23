"""PreCompact hook: save a mechanical fallback note before the context is compacted.

Safety net for when no /handoff was written in time. Records the recent user requests and the
files written or edited, to docs/handoffs/auto/ (excluded from the index; not curated).
Always exits 0 so compaction is never blocked.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from handoff_common import AUTO, context_tokens, read_entries

MAX_PROMPTS = 12
MAX_CHARS = 600


def user_prompts(entries: list[dict]) -> list[str]:
    out = []
    for d in entries:
        m = d.get("message")
        if d.get("type") != "user" or d.get("isMeta") or not isinstance(m, dict):
            continue
        c = m.get("content")
        texts = [c] if isinstance(c, str) else [b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text"]
        for t in texts:
            t = t.strip()
            if t and not t.startswith("<"):  # skip command wrappers, reminders and tool output
                out.append(t if len(t) <= MAX_CHARS else t[:MAX_CHARS] + " [...]")
    return out[-MAX_PROMPTS:]


def touched_files(entries: list[dict]) -> list[str]:
    seen: dict[str, None] = {}
    for d in entries:
        m = d.get("message")
        for b in (m.get("content") if isinstance(m, dict) else None) or []:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Write", "Edit", "NotebookEdit"):
                p = (b.get("input") or {}).get("file_path") or (b.get("input") or {}).get("notebook_path")
                if p:
                    seen[p] = None
    return list(seen)


def main() -> int:
    try:
        event = json.load(sys.stdin)
        entries = read_entries(Path(event["transcript_path"]), tail=None)
        now = datetime.now()
        AUTO.mkdir(parents=True, exist_ok=True)
        path = AUTO / f"{now:%Y-%m-%d-%H%M}-{event.get('trigger', 'compact')}.md"
        prompts = "\n".join(f"{i}. {p}" for i, p in enumerate(user_prompts(entries), 1)) or "(none found)"
        files = "\n".join(f"- `{f}`" for f in touched_files(entries)) or "- (none)"
        path.write_text(
            f"---\ndate: {now:%Y-%m-%d %H:%M}\nproject: {event.get('cwd', '')}\nsession: {event.get('session_id', '')}\n"
            f"trigger: {event.get('trigger', '')}\ncontext_tokens: {context_tokens(entries)}\n"
            f"transcript: {event.get('transcript_path', '')}\n---\n\n"
            f"# Pre-compaction snapshot (automatic)\n\n"
            f"Mechanical fallback, not a curated handoff. Prefer a /handoff note when one exists.\n\n"
            f"## Recent user requests (oldest first)\n{prompts}\n\n"
            f"## Files written or edited this session\n{files}\n",
            encoding="utf-8",
        )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

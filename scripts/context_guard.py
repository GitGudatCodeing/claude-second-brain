"""UserPromptSubmit hook: tell Claude when the session's context passes the handoff thresholds.

Thresholds live in .claude/handoff.json. Soft fires once per session; hard fires on every prompt
until the context drops (new session or compaction). Never blocks the prompt; always exits 0.
  python scripts/context_guard.py                   hook mode (JSON on stdin)
  python scripts/context_guard.py --check <jsonl>   print the context size of a transcript
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from handoff_common import context_tokens, load_config, read_entries

STATE = Path(tempfile.gettempdir()) / "secondbrain-handoff"

SOFT_MSG = (
    "Context guard: this session is at ~{k}k tokens (soft limit {soft}k). "
    "Finish the current step, then tell the user once and suggest /handoff to continue in a fresh session. "
    "Do not interrupt work in progress for this."
)
HARD_MSG = (
    "Context guard: this session is at ~{k}k tokens (hard limit {hard}k). "
    "Before other work, run the /handoff workflow (.claude/commands/handoff.md): "
    "write the handoff note and propose the new session. Then answer the user's message briefly."
)


def main() -> int:
    if "--check" in sys.argv:
        print(context_tokens(read_entries(Path(sys.argv[-1]))))
        return 0
    try:
        event = json.load(sys.stdin)
        cfg = load_config()
        tokens = context_tokens(read_entries(Path(event["transcript_path"])))
    except Exception:
        return 0  # a broken guard must never block a prompt; invariants.py reports config problems
    level = "hard" if tokens >= cfg["hard"] else "soft" if tokens >= cfg["soft"] else None
    marker = STATE / f"{event.get('session_id', 'unknown')}.soft"
    if level is None:
        marker.unlink(missing_ok=True)  # dropped below soft (compaction): allow a new soft notice later
        return 0
    if level == "soft":
        if marker.exists():
            return 0
        STATE.mkdir(exist_ok=True)
        marker.touch()
    msg = (HARD_MSG if level == "hard" else SOFT_MSG).format(
        k=tokens // 1000, soft=cfg["soft"] // 1000, hard=cfg["hard"] // 1000
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": msg}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

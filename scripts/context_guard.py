"""UserPromptSubmit and PostToolUse hook: require a handoff when the session's context passes the hard limit.

The limit lives in .claude/handoff.json. Below it the hook is silent. At or above it, UserPromptSubmit
fires on every prompt until the context drops (new session or compaction), and PostToolUse fires once
per session, so a long autonomous turn learns about it mid-turn instead of at the next prompt.
PostToolUse runs async: its output reaches the model with a later tool result and adds no wait.
Never blocks; always exits 0.
  python scripts/context_guard.py                   hook mode (JSON on stdin)
  python scripts/context_guard.py --check <jsonl>   print the context size of a transcript
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

from handoff_common import context_tokens, load_config, read_entries

STATE = Path(tempfile.gettempdir()) / "secondbrain-context-guard"
HARD_MSG = (
    "Context guard: this session is at ~{k}k tokens (hard limit {hard}k). "
    "Before other work, run the /handoff workflow (.claude/commands/handoff.md): "
    "write the handoff note and propose the new session as a card. Then answer the user's message briefly."
)
MID_TURN_MSG = (
    "Context guard: this session passed ~{k}k tokens mid-turn (hard limit {hard}k). "
    "Finish the current step, then run the /handoff workflow (.claude/commands/handoff.md): "
    "write the handoff note, propose the new session as a card and stop working here."
)


def first_mid_turn_notice(session_id: str) -> bool:
    """True once per session; later PostToolUse calls stay silent."""
    marker = STATE / re.sub(r"[^\w-]", "_", session_id or "unknown")
    if marker.exists():
        return False
    STATE.mkdir(exist_ok=True)
    marker.touch()
    return True


def main() -> int:
    if "--check" in sys.argv:
        print(context_tokens(read_entries(Path(sys.argv[-1]))))
        return 0
    try:
        event = json.load(sys.stdin)
        cfg = load_config()
        tokens = context_tokens(read_entries(Path(event["transcript_path"])))
        name = event.get("hook_event_name", "UserPromptSubmit")
        if tokens < cfg["hard"]:
            return 0
        if name == "PostToolUse":
            if not first_mid_turn_notice(event.get("session_id", "")):
                return 0
            template = MID_TURN_MSG
        else:
            name, template = "UserPromptSubmit", HARD_MSG
    except Exception:
        return 0  # a broken guard must never block a prompt; invariants.py reports config problems
    msg = template.format(k=tokens // 1000, hard=cfg["hard"] // 1000)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": name, "additionalContext": msg}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

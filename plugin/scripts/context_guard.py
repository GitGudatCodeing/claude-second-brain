"""UserPromptSubmit and PostToolUse hook: require a handoff when the session's context passes the hard limit.

Idle nudge: on UserPromptSubmit below the hard limit, if the context is at least idle_min_tokens and the last
reply is older than idle_minutes, the prompt cache has expired and this turn re-sends the whole context at
full price. A fresh session then costs little extra, so the guard asks Claude to offer a handoff (not require it).

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
from datetime import datetime, timezone
from pathlib import Path

from handoff_common import context_tokens, last_reply_time, load_config, read_entries

STATE = Path(tempfile.gettempdir()) / "secondbrain-context-guard"
HARD_MSG = (
    "Context guard: this session is at ~{k}k tokens (hard limit {hard}k). "
    "Before other work, run the /second-brain:handoff workflow: "
    "write the handoff note and propose the new session as a card. Then answer the user's message briefly."
)
MID_TURN_MSG = (
    "Context guard: this session passed ~{k}k tokens mid-turn (hard limit {hard}k). "
    "Finish the current step, then run the /second-brain:handoff workflow: "
    "write the handoff note, propose the new session as a card and stop working here."
)

IDLE_MSG = (
    "Context guard: this session is at ~{k}k tokens and was idle for {m} min, so the prompt cache expired "
    "and this turn re-sends the whole context at full price. A fresh session costs little extra now. "
    "Before other work, ask the user in one short question whether to hand off. "
    "If yes, run the /second-brain:handoff workflow; if no, carry on."
)


def idle_minutes(entries: list[dict]) -> int:
    last = last_reply_time(entries)
    return int((datetime.now(timezone.utc) - last).total_seconds() // 60) if last else 0


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
        entries = read_entries(Path(event["transcript_path"]))
        tokens = context_tokens(entries)
        name = event.get("hook_event_name", "UserPromptSubmit")
        if tokens < cfg["hard"]:
            if name == "PostToolUse" or tokens < cfg["idle_min"]:
                return 0
            idle = idle_minutes(entries)
            if idle < cfg["idle_minutes"]:
                return 0
            msg = IDLE_MSG.format(k=tokens // 1000, m=idle)
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": msg}}))
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

"""UserPromptSubmit hook: require a handoff when the session's context passes the hard limit.

The limit lives in .claude/handoff.json. Below it the hook is silent; at or above it, it fires
on every prompt until the context drops (new session or compaction). Never blocks the prompt;
always exits 0.
  python scripts/context_guard.py                   hook mode (JSON on stdin)
  python scripts/context_guard.py --check <jsonl>   print the context size of a transcript
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from handoff_common import context_tokens, load_config, read_entries

HARD_MSG = (
    "Context guard: this session is at ~{k}k tokens (hard limit {hard}k). "
    "Before other work, run the /handoff workflow (.claude/commands/handoff.md): "
    "write the handoff note and propose the new session as a card. Then answer the user's message briefly."
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
    if tokens < cfg["hard"]:
        return 0
    msg = HARD_MSG.format(k=tokens // 1000, hard=cfg["hard"] // 1000)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": msg}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Shared helpers for the handoff hooks (context_guard.py, precompact_snapshot.py). Standard library only."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

# The project the hook runs for. As a plugin, this script lives in the plugin cache, not the project.
ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parent.parent)
CONFIG = ROOT / ".claude/handoff.json"
HANDOFFS = ROOT / "docs/handoffs"
AUTO = HANDOFFS / "auto"
DEFAULT_HARD = 250_000  # used when the project has no .claude/handoff.json
DEFAULT_IDLE_MIN = 150_000  # idle nudge: smallest context worth a fresh start after the cache expired
DEFAULT_IDLE_MINUTES = 60  # prompt cache TTL (1h)
TAIL_BYTES = 4_000_000  # usage is on every assistant message, so the tail is enough


def load_config() -> dict:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    return {
        "hard": int(cfg.get("hard_tokens", DEFAULT_HARD)),
        "idle_min": int(cfg.get("idle_min_tokens", DEFAULT_IDLE_MIN)),
        "idle_minutes": int(cfg.get("idle_minutes", DEFAULT_IDLE_MINUTES)),
    }


def read_entries(transcript: Path, tail: int | None = TAIL_BYTES) -> list[dict]:
    """Transcript JSONL entries (main thread only). With `tail`, reads only the last bytes."""
    with transcript.open("rb") as f:
        if tail:
            size = f.seek(0, 2)
            f.seek(max(0, size - tail))
        raw = f.read().decode("utf-8", errors="ignore")
    out = []
    for line in raw.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue  # first line of a tail read is usually partial
        if isinstance(d, dict) and not d.get("isSidechain"):
            out.append(d)
    return out


def last_reply_time(entries: list[dict]) -> datetime | None:
    """Timestamp of the latest assistant entry (the end of the last request), UTC."""
    for d in reversed(entries):
        if d.get("type") == "assistant" and d.get("timestamp"):
            try:
                return datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
            except ValueError:
                return None
    return None


def context_tokens(entries: list[dict]) -> int:
    """Tokens sent with the latest request: input + cache read + cache write. 0 if unknown."""
    for d in reversed(entries):
        m = d.get("message")
        u = m.get("usage") if isinstance(m, dict) else None
        if u:
            return u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
    return 0

"""Shared helpers for the handoff hooks (context_guard.py, precompact_snapshot.py). Standard library only."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".claude/handoff.json"
HANDOFFS = ROOT / "docs/handoffs"
AUTO = HANDOFFS / "auto"
TAIL_BYTES = 4_000_000  # usage is on every assistant message, so the tail is enough


def load_config() -> dict:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    return {"soft": int(cfg["soft_tokens"]), "hard": int(cfg["hard_tokens"])}


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


def context_tokens(entries: list[dict]) -> int:
    """Tokens sent with the latest request: input + cache read + cache write. 0 if unknown."""
    for d in reversed(entries):
        m = d.get("message")
        u = m.get("usage") if isinstance(m, dict) else None
        if u:
            return u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
    return 0

"""Report context size per Claude Code session, to tune the handoff limit in .claude/handoff.json.

Reads every transcript under ~/.claude/projects/. Context per call is input + cache read + cache
write of the main thread (subagents excluded). Sessions without assistant usage are skipped.
  python scripts/session_sizes.py                  all sessions
  python scripts/session_sizes.py --since 2026-10-24
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from handoff_common import load_config

BANDS = (200_000, 300_000, 350_000, 450_000)


def session(path: Path) -> tuple[str, list[int]]:
    # One API call is written as several entries (one per content block) sharing message.id, and resumed
    # sessions replay old entries; about 60% of entries are such copies, so count each message.id once.
    first, ctx, seen = "", [], set()
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            first = first or e.get("timestamp", "")
            m = e.get("message")
            if e.get("type") != "assistant" or e.get("isSidechain") or not isinstance(m, dict):
                continue
            mid = m.get("id")
            if mid and mid in seen:
                continue
            seen.add(mid)
            u = m.get("usage") or {}
            c = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            if c:
                ctx.append(c)
    return first[:10], ctx


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="", help="YYYY-MM-DD, first message on or after")
    args = ap.parse_args()
    hard = load_config()["hard"]

    rows = []
    for p in Path.home().glob(".claude/projects/*/*.jsonl"):
        date, ctx = session(p)
        if ctx and date >= args.since:
            rows.append((date, p.parent.name[-28:], max(ctx), ctx))
    rows.sort()

    print(f"{'date':10} {'project':28} {'peak':>8} {'calls':>6}")
    for date, proj, peak, ctx in rows:
        print(f"{date:10} {proj:28} {peak:8} {len(ctx):6}{'  cap' if peak >= hard else ''}")

    total = sum(sum(r[3]) for r in rows) or 1
    print(f"\n{len(rows)} sessions, hard limit {hard // 1000}k, reached by {sum(r[2] >= hard for r in rows)}")
    for b in BANDS:
        over = sum(r[2] > b for r in rows)
        share = sum(c for r in rows for c in r[3] if c > b) / total
        print(f"  >{b // 1000}k: {over} sessions, {share:.0%} of context tokens")


if __name__ == "__main__":
    main()

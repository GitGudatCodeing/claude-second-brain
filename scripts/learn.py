"""Record lessons as dated, supersedable directives in docs/lessons.md.

Usage:
  python scripts/learn.py "<lesson as a directive>" --cause "<root cause>" --detect "<how to catch it>" [--tags a,b]
  python scripts/learn.py --supersede L-0003 "<new lesson>" --cause ... --detect ... [--tags ...]
  python scripts/learn.py --retire L-0003 --reason "<why>"
  python scripts/learn.py --list [--all]

Standard library only. Adding the same active lesson twice is a no-op.
After writing, the file is re-indexed through mcp/reindex_hook.py (best effort).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LESSONS = ROOT / "docs" / "lessons.md"
HEADER = (
    "# Lessons\n\n"
    "Directives learned from corrections, failed approaches and false assumptions.\n"
    "Written by `scripts/learn.py` (use `/learn`). Never delete entries; supersede or retire them.\n"
)
ENTRY = re.compile(r"^## (L-\d{4}) · (\d{4}-\d{2}-\d{2}) · (.+)$", re.M)


def load() -> str:
    if not LESSONS.exists():
        LESSONS.parent.mkdir(parents=True, exist_ok=True)
        LESSONS.write_text(HEADER, encoding="utf-8")
    return LESSONS.read_text(encoding="utf-8")


def entries(text: str) -> list[dict]:
    out = []
    matches = list(ENTRY.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end]
        lesson = re.search(r"^\*\*Lesson:\*\* (.*)$", body, re.M)
        out.append({
            "id": m.group(1), "date": m.group(2), "status": m.group(3).strip(),
            "lesson": lesson.group(1).strip() if lesson else "",
            "start": m.start(), "header_end": m.end(),
        })
    return out


def next_id(es: list[dict]) -> str:
    n = max((int(e["id"][2:]) for e in es), default=0) + 1
    return f"L-{n:04d}"


def set_status(text: str, entry_id: str, status: str) -> str:
    def repl(m: re.Match) -> str:
        return f"## {m.group(1)} · {m.group(2)} · {status}" if m.group(1) == entry_id else m.group(0)
    return ENTRY.sub(repl, text)


def reindex() -> None:
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(LESSONS)}})
    try:
        subprocess.run(
            ["uv", "run", "--project", str(ROOT / "mcp"), "python", str(ROOT / "mcp" / "reindex_hook.py")],
            input=payload, text=True, timeout=120, capture_output=True,
        )
    except Exception as e:  # indexing is a convenience; the file is the record
        print(f"note: re-index skipped ({e}); run index_paths later", file=sys.stderr)


def add(text: str, args, today: str, supersedes: str | None = None) -> tuple[str, str]:
    es = entries(text)
    for e in es:
        if e["status"] == "active" and e["lesson"].lower() == args.lesson.strip().lower():
            return text, f"no-op: already recorded as {e['id']}"
    new_id = next_id(es)
    lines = [
        f"\n## {new_id} · {today} · active",
        f"**Lesson:** {args.lesson.strip()}",
        f"**Cause:** {args.cause.strip()}",
        f"**Detect:** {args.detect.strip()}",
    ]
    if args.tags:
        lines.append(f"**Tags:** {', '.join(t.strip() for t in args.tags.split(',') if t.strip())}")
    if supersedes:
        lines.append(f"**Supersedes:** {supersedes}")
    return text.rstrip("\n") + "\n" + "\n".join(lines) + "\n", f"recorded {new_id}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lesson", nargs="?")
    ap.add_argument("--cause")
    ap.add_argument("--detect")
    ap.add_argument("--tags")
    ap.add_argument("--supersede", metavar="ID")
    ap.add_argument("--retire", metavar="ID")
    ap.add_argument("--reason")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--all", action="store_true", help="with --list, include superseded/retired")
    args = ap.parse_args()
    today = dt.date.today().isoformat()
    text = load()

    if args.list:
        for e in entries(text):
            if args.all or e["status"] == "active":
                print(f"{e['id']}  {e['date']}  [{e['status']}]  {e['lesson']}")
        return 0

    if args.retire:
        if not args.reason:
            ap.error("--retire needs --reason")
        if args.retire not in {e["id"] for e in entries(text)}:
            ap.error(f"unknown id {args.retire}")
        text = set_status(text, args.retire, f"retired {today}: {args.reason.strip()}")
        LESSONS.write_text(text, encoding="utf-8")
        reindex()
        print(f"retired {args.retire}")
        return 0

    if not (args.lesson and args.cause and args.detect):
        ap.error("a lesson needs the lesson text, --cause and --detect")

    if args.supersede:
        if args.supersede not in {e["id"] for e in entries(text)}:
            ap.error(f"unknown id {args.supersede}")
        text, msg = add(text, args, today, supersedes=args.supersede)
        new_id = msg.split()[-1]
        text = set_status(text, args.supersede, f"superseded by {new_id} ({today})")
        msg += f", superseding {args.supersede}"
    else:
        text, msg = add(text, args, today)

    if not msg.startswith("no-op"):
        LESSONS.write_text(text, encoding="utf-8")
        reindex()
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())

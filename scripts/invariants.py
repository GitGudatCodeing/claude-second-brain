"""Invariants: check that every SecondBrain pipeline is wired to its consumer.

Standard library only, no model load, so it is cheap enough for every session start.
  python scripts/invariants.py          full report, exit 1 on any failure
  python scripts/invariants.py --hook   SessionStart mode: one line on success,
                                        failures listed for Claude; always exit 0
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
MCP_HOME = HOME / ".mcp-memory"
INDEX_DB = Path(os.environ.get("VAULT_INDEX_DB", MCP_HOME / "vault-index.db"))  # same default as server.py
# Where the two MCP servers may be registered, first match wins: the project's .mcp.json
# (Claude Code), then Claude Desktop (Windows Store, Windows, macOS, Linux).
MCP_CONFIG_GLOBS = [
    str(ROOT / ".mcp.json"),
    str(HOME / "AppData/Local/Claude-Data/claude_*/claude_desktop_config.json"),
    str(HOME / "AppData/Roaming/Claude/claude_desktop_config.json"),
    str(HOME / "Library/Application Support/Claude/claude_desktop_config.json"),
    str(HOME / ".config/Claude/claude_desktop_config.json"),
]
INDEXED_EXT = {
    ".md", ".markdown", ".txt", ".rst", ".py", ".js", ".ts", ".tsx", ".jsx", ".cs", ".java",
    ".go", ".rs", ".sql", ".json", ".yaml", ".yml", ".toml", ".ps1", ".sh",
}  # mirrors mcp/server.py EXTENSIONS; checked by check_index_mirror
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "bin", "obj",
    "dist", "build", ".idea", ".vs", ".next", ".obsidian", ".trash",
}  # mirrors mcp/server.py SKIP_DIRS; checked by check_index_mirror
ALWAYS_LOADED_TOKEN_BUDGET = 10_000
SKILL_LISTING_TOKEN_BUDGET = 5_500  # ~4.5k measured without audit-suite (2026-10-28), plus headroom
TRANSCRIPTS = HOME / ".claude/projects" / re.sub(r"[:\\/]", "-", str(ROOT))

results: list[tuple[bool, str, str]] = []


def check(name: str):
    def wrap(fn):
        def run():
            try:
                problems = fn() or []
            except Exception as e:  # a crashing check is a failing check
                problems = [f"check crashed: {type(e).__name__}: {e}"]
            results.append((not problems, name, "; ".join(problems)))
        CHECKS.append(run)
        return fn
    return wrap


CHECKS: list = []


def desktop_config() -> tuple[Path | None, dict | None]:
    for pattern in MCP_CONFIG_GLOBS:
        hits = glob.glob(pattern)
        if len(hits) == 1:
            p = Path(hits[0])
            return p, json.loads(p.read_text(encoding="utf-8"))
    return None, None


def abs_paths(cmd: str) -> list[str]:
    """Absolute paths in a command line, with $CLAUDE_PROJECT_DIR expanded to this folder."""
    cmd = cmd.replace('"$CLAUDE_PROJECT_DIR"', ROOT.as_posix()).replace("$CLAUDE_PROJECT_DIR", ROOT.as_posix())
    return [t.strip("\"'") for t in cmd.split() if re.match(r"^[\"']?([A-Za-z]:/|/)", t)]


@check("desktop-config: both MCP servers registered and launchable")
def check_desktop_config():
    p, cfg = desktop_config()
    if p is None:
        return ["no MCP config found; copy .mcp.json.example to .mcp.json or register the servers in Claude Desktop"]
    servers = cfg.get("mcpServers", {})
    out = []
    for name in ("memory", "vault-index"):
        s = servers.get(name)
        if not s:
            out.append(f"server '{name}' missing in {p}")
            continue
        if not (Path(s["command"]).is_file() or shutil.which(s["command"])):
            out.append(f"{name}: command not found: {s['command']}")
        for a in s.get("args", []):
            if re.match(r"^([A-Za-z]:[\\/]|/)", a) and not Path(a).exists():
                out.append(f"{name}: path arg missing: {a}")
    mem = (servers.get("memory") or {}).get("env", {}).get("MEMORY_FILE_PATH")
    if mem and not Path(mem).parent.is_dir():
        out.append(f"memory: MEMORY_FILE_PATH folder missing: {mem}")
    return out


@check("memory-graph: file parses and source paths exist")
def check_memory_graph():
    _, cfg = desktop_config()
    mem = ((cfg or {}).get("mcpServers", {}).get("memory") or {}).get("env", {}).get("MEMORY_FILE_PATH")
    if not mem:
        return ["MEMORY_FILE_PATH not set in desktop config"]
    p = Path(mem)
    if not p.exists():
        return []  # created on first write; not an error
    out, names = [], set()
    lessons = lesson_ids()
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("type") == "entity":
            names.add(rec["name"])
            for obs in rec.get("observations", []):
                m = re.search(r"source: (.+?)\s*$", obs)
                if m and not (ROOT / m.group(1)).exists():  # relative sources are relative to ROOT
                    out.append(f"{rec['name']}: source missing: {m.group(1)}")
                for lid in re.findall(r"L-\d{4}", obs):
                    if lid not in lessons:
                        out.append(f"{rec['name']}: refers to unknown lesson {lid}")
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("type") == "relation" and not {rec["from"], rec["to"]} <= names:
                out.append(f"relation {rec['from']} -> {rec['to']} points at a missing entity")
    return out


@check("reindex-hook: configured, forward-slash paths, script present")
def check_hook():
    s = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    cmds = [h["command"] for g in s.get("hooks", {}).get("PostToolUse", []) for h in g.get("hooks", [])]
    hook = [c for c in cmds if "reindex_hook.py" in c]
    if not hook:
        return ["no PostToolUse hook runs reindex_hook.py"]
    out = []
    for c in hook:
        if "\\" in c:
            out.append("hook command contains backslashes (Git Bash strips them; see L-0003)")
        for path in abs_paths(c):
            if not Path(path).exists():
                out.append(f"hook path missing: {path}")
    if not (ROOT / "mcp/.venv").is_dir():
        out.append("mcp/.venv missing; run `uv sync` in mcp/")
    return out


def hook_commands(settings: Path, event: str) -> list[str]:
    if not settings.is_file():
        return []
    s = json.loads(settings.read_text(encoding="utf-8"))
    return [h["command"] for g in s.get("hooks", {}).get(event, []) for h in g.get("hooks", [])]


@check("handoff: guard and snapshot hooks configured once, threshold valid, command present")
def check_handoff():
    out = []
    user_settings, project_settings = HOME / ".claude/settings.json", ROOT / ".claude/settings.json"
    for event, script in (("UserPromptSubmit", "context_guard.py"), ("PostToolUse", "context_guard.py"),
                          ("PreCompact", "precompact_snapshot.py")):
        in_user = [c for c in hook_commands(user_settings, event) if script in c]
        in_project = [c for c in hook_commands(project_settings, event) if script in c]
        hook = in_user + in_project
        if not hook:
            out.append(f"no {event} hook runs {script} (user or project settings)")
        if in_user and in_project:
            out.append(f"{script} runs from both user and project settings; remove it from .claude/settings.json")
        for c in hook:
            if "\\" in c:
                out.append(f"{script} hook command contains backslashes (see L-0003)")
            for path in abs_paths(c):
                if not Path(path).exists():
                    out.append(f"hook path missing: {path}")
    cfg = json.loads((ROOT / ".claude/handoff.json").read_text(encoding="utf-8"))
    if not isinstance(cfg.get("hard_tokens"), int) or cfg["hard_tokens"] <= 0:
        out.append("handoff.json: hard_tokens must be a positive integer")
    if not any((d / "handoff.md").is_file() for d in (ROOT / ".claude/commands", HOME / ".claude/commands")):
        out.append("handoff.md missing from .claude/commands and ~/.claude/commands (/handoff command)")
    if "docs/handoffs/auto" not in ignores_for(ROOT):
        out.append(".indexignore must exclude docs/handoffs/auto (raw prompt snapshots)")
    return out


def ignores_for(root: Path) -> list[str]:
    """Same parsing as mcp/server.py load_ignores."""
    f = root / ".indexignore"
    if not root.is_dir() or not f.is_file():
        return []
    lines = (l.split("#", 1)[0].strip().replace("\\", "/").strip("/") for l in f.read_text(encoding="utf-8").splitlines())
    return [l.lower() for l in lines if l]


def ignored(p: Path, root: Path, igs: list[str]) -> bool:
    try:
        rel = p.relative_to(root).as_posix().lower()
    except ValueError:
        return False
    return any(rel == ig or rel.startswith(ig + "/") for ig in igs)


def walk(root: Path):
    """Same traversal as mcp/server.py iter_files."""
    if root.is_file():
        yield root
        return
    igs = ignores_for(root)
    for d, dirs, fs in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not ignored(Path(d) / x, root, igs)]
        for f in fs:
            if not ignored(Path(d) / f, root, igs):
                yield Path(d) / f


@check("vault-index: sources exist, index fresh, chunk tables in sync")
def check_index():
    if not INDEX_DB.exists():
        return [f"index DB missing: {INDEX_DB}"]
    con = sqlite3.connect(f"file:{INDEX_DB}?mode=ro", uri=True)
    out = []
    sources = [r[0] for r in con.execute("SELECT path FROM sources")]
    if str(ROOT) not in sources:
        out.append(f"{ROOT} is not a registered source")
    indexed = {p: m for p, m in con.execute("SELECT path, mtime FROM files")}
    stale, missing = [], []
    for s in sources:
        root = Path(s)
        if not root.exists():
            out.append(f"source no longer exists: {s}")
            continue
        for f in walk(root):
            if f.suffix.lower() not in INDEXED_EXT or f.stat().st_size > 1_000_000:
                continue
            m = indexed.get(str(f))
            if m is None:
                missing.append(f.name)
            elif f.stat().st_mtime > m + 1e-6:
                stale.append(f.name)
    gone = [p for p in indexed if not Path(p).exists()]
    excluded = [
        p for s in sources for igs in [ignores_for(Path(s))] for p in indexed
        if igs and ignored(Path(p), Path(s), igs)
    ]
    drift = []
    if missing:
        drift.append(f"{len(missing)} file(s) not indexed: {', '.join(sorted(missing)[:5])}")
    if stale:
        drift.append(f"{len(stale)} file(s) changed since indexing: {', '.join(sorted(stale)[:5])}")
    if gone:
        drift.append(f"{len(gone)} deleted file(s) still indexed")
    if excluded:
        drift.append(f"{len(excluded)} file(s) listed in .indexignore still indexed")
    if drift:
        drift[-1] += " -> run index_paths with no arguments"
        out += drift
    n_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    n_fts = con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    n_vec = con.execute("SELECT COUNT(*) FROM chunks_vec_rowids").fetchone()[0]
    if not n_chunks == n_fts == n_vec:
        out.append(f"chunk tables out of sync: chunks={n_chunks} fts={n_fts} vec={n_vec}")
    return out


@check("vault-index: invariant's extension and skip lists mirror server.py")
def check_index_mirror():
    src = (ROOT / "mcp/server.py").read_text(encoding="utf-8")
    out = []
    for const, mine in (("EXTENSIONS", INDEXED_EXT), ("SKIP_DIRS", SKIP_DIRS)):
        m = re.search(const + r" = \{(.*?)\}", src, re.S)
        theirs = set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()
        if theirs != mine:
            out.append(f"{const} differs from server.py: {sorted(theirs ^ mine)}")
    return out


@check("eval: golden labels point at existing files and headings; golden set not indexed")
def check_golden():
    golden = ROOT / "eval/golden.jsonl"
    if not golden.exists():
        return ["eval/golden.jsonl missing"]
    out = []
    if golden.suffix in INDEXED_EXT:
        out.append("golden set has an indexed extension; its questions would match themselves")
    heading_re = re.compile(r"^#{1,6}\s+(.*)$", re.M)
    for line in golden.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        q = json.loads(line)
        for lab in q["relevant"]:
            f = ROOT / lab["path"]
            if not f.exists():
                out.append(f"{q['id']}: label file missing: {lab['path']}")
            elif lab["heading"] and not any(lab["heading"] in h for h in heading_re.findall(f.read_text(encoding="utf-8"))):
                out.append(f"{q['id']}: heading '{lab['heading']}' no longer in {lab['path']}")
    return out


def lesson_ids() -> dict[str, str]:
    p = ROOT / "docs/lessons.md"
    if not p.exists():
        return {}
    return dict(re.findall(r"^## (L-\d{4}) · \d{4}-\d{2}-\d{2} · (.+)$", p.read_text(encoding="utf-8"), re.M))


@check("lessons: well-formed, unique ids, supersede links valid")
def check_lessons():
    p = ROOT / "docs/lessons.md"
    text = p.read_text(encoding="utf-8")
    ids = re.findall(r"^## (L-\d{4}) ", text, re.M)
    out = []
    if len(ids) != len(set(ids)):
        out.append("duplicate lesson ids")
    statuses = lesson_ids()
    for lid, st in statuses.items():
        if not re.match(r"^(active|superseded by L-\d{4} \(\d{4}-\d{2}-\d{2}\)|retired \d{4}-\d{2}-\d{2}: .+)$", st):
            out.append(f"{lid}: bad status '{st}'")
        m = re.match(r"superseded by (L-\d{4})", st)
        if m and m.group(1) not in statuses:
            out.append(f"{lid}: superseded by unknown {m.group(1)}")
    blocks = re.split(r"^## L-\d{4} .*$", text, flags=re.M)[1:]
    for lid, b in zip(ids, blocks, strict=True):
        for field in ("Lesson", "Cause", "Detect"):
            if f"**{field}:**" not in b:
                out.append(f"{lid}: missing {field}")
    return out


@check("claude-md: commands it lists exist, and every command is listed")
def check_commands():
    md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^- `/([a-z-]+)", md, re.M))
    files = {p.stem for p in (ROOT / ".claude/commands").glob("*.md")}
    user_files = {p.stem for p in (HOME / ".claude/commands").glob("*.md")}
    out = [f"/{c} listed in CLAUDE.md but no command file" for c in sorted(listed - files - user_files)]
    out += [f"/{c} exists but is not listed in CLAUDE.md" for c in sorted(files - listed)]
    for rel in re.findall(r"`((?:docs|mcp|scripts|\.claude)/[^`*]+?)`", md):
        if not (ROOT / rel.rstrip("/")).exists():
            out.append(f"CLAUDE.md points to missing path: {rel}")
    return out


@check(f"context-budget: always-loaded files under {ALWAYS_LOADED_TOKEN_BUDGET} tokens")
def check_budget():
    files = [ROOT / "CLAUDE.md", HOME / ".claude/CLAUDE.md"]
    chars = sum(len(f.read_text(encoding="utf-8")) for f in files if f.exists())
    tokens = chars // 4  # rough estimate for English markdown
    return [] if tokens < ALWAYS_LOADED_TOKEN_BUDGET else [f"~{tokens} tokens"]


def latest_skill_listing(transcripts: Path, since: float) -> str | None:
    """Content of the newest skill_listing written after `since`, from the newest transcript that has one."""
    for t in sorted(transcripts.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True):
        if t.stat().st_mtime < since:
            return None
        found = None
        with t.open(encoding="utf-8") as f:
            for line in f:
                if '"skill_listing"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                a = d.get("attachment") or {}
                ts = datetime.fromisoformat(d.get("timestamp", "1970-01-01T00:00:00Z").replace("Z", "+00:00"))
                if a.get("type") == "skill_listing" and ts.timestamp() >= since:
                    found = a.get("content", "")
        if found is not None:
            return found
    return None


@check(f"context-budget: skill listing under {SKILL_LISTING_TOKEN_BUDGET} tokens")
def check_skill_listing():
    # Sessions started before the last settings change do not reflect it (e.g. a plugin just disabled).
    content = latest_skill_listing(TRANSCRIPTS, (ROOT / ".claude/settings.json").stat().st_mtime)
    if content is None:
        return []  # no session since the last settings change; nothing to measure yet
    tokens = len(content) // 4
    return [] if tokens < SKILL_LISTING_TOKEN_BUDGET else [f"~{tokens} tokens; disable unused plugins in .claude/settings.json (account-synced plugins: in the app's plugin settings)"]


def main() -> int:
    hook = "--hook" in sys.argv
    for run in CHECKS:
        run()
    failed = [r for r in results if not r[0]]
    if hook:
        if not failed:
            print(f"SecondBrain invariants: {len(results)}/{len(results)} ok")
        else:
            print(f"SecondBrain invariants: {len(failed)} of {len(results)} FAILED. Tell the user, then fix the root cause:")
            for _, name, detail in failed:
                print(f"- {name}: {detail}")
        return 0
    for ok, name, detail in results:
        print(f"[{'ok' if ok else 'FAIL'}] {name}" + ("" if ok else f"\n       {detail}"))
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

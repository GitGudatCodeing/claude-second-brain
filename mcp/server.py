"""Vault index MCP server: hybrid keyword (FTS5) + vector (sqlite-vec) search.

Embeddings come from fastembed (ONNX, CPU). Everything lives in one SQLite file.
Env:
  VAULT_INDEX_DB     path to the SQLite file (default ~/.mcp-memory/vault-index.db)
  VAULT_MODEL_CACHE  fastembed model cache dir (default ~/.mcp-memory/models)
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import sys
from pathlib import Path

import sqlite_vec
from mcp.server.fastmcp import FastMCP

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIM = 384
HOME = Path.home() / ".mcp-memory"
DB_PATH = Path(os.environ.get("VAULT_INDEX_DB", HOME / "vault-index.db"))
MODEL_CACHE = Path(os.environ.get("VAULT_MODEL_CACHE", HOME / "models"))

EXTENSIONS = {
    ".md", ".markdown", ".txt", ".rst",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".cs", ".java", ".go", ".rs", ".sql",
    ".json", ".yaml", ".yml", ".toml", ".ps1", ".sh",
}
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "bin", "obj",
    "dist", "build", ".idea", ".vs", ".next", ".obsidian", ".trash",
}
MAX_FILE_BYTES = 1_000_000
CHUNK_CHARS = 1200

mcp = FastMCP("vault-index")
_embedder = None
_db: sqlite3.Connection | None = None


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def embedder():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding

        MODEL_CACHE.mkdir(parents=True, exist_ok=True)
        _embedder = TextEmbedding(MODEL_NAME, cache_dir=str(MODEL_CACHE))
    return _embedder


def embed(texts: list[str]) -> list[bytes]:
    return [sqlite_vec.serialize_float32(v.tolist()) for v in embedder().embed(texts)]


def db() -> sqlite3.Connection:
    global _db
    if _db is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")  # the PostToolUse hook writes concurrently
        con.enable_load_extension(True)
        sqlite_vec.load(con)
        con.enable_load_extension(False)
        con.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS sources(path TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS files(
                id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL,
                mtime REAL NOT NULL, hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS chunks(
                id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL,
                ord INTEGER NOT NULL, heading TEXT NOT NULL, text TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS chunks_file ON chunks(file_id);
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, heading);
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(embedding float[{DIM}]);
            """
        )
        _db = con
    return _db


# ---------- chunking ----------

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def chunk_text(text: str, is_markdown: bool) -> list[tuple[str, str]]:
    """Return (heading_path, chunk_text) pairs."""
    sections: list[tuple[str, list[str]]] = []
    stack: list[tuple[int, str]] = []
    heading, buf = "", []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if (in_fence or not is_markdown) else _HEADING.match(line)
        if m:
            sections.append((heading, buf))
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2).strip()))
            heading, buf = " > ".join(h for _, h in stack), []
        else:
            buf.append(line)
    sections.append((heading, buf))

    out: list[tuple[str, str]] = []
    for head, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        cur = ""
        for para in re.split(r"\n\s*\n", body):
            while len(para) > CHUNK_CHARS * 1.5:  # very long paragraph/code block
                cut = para.rfind("\n", 0, CHUNK_CHARS)
                cut = cut if cut > CHUNK_CHARS // 2 else CHUNK_CHARS
                if cur:
                    out.append((head, cur)); cur = ""
                out.append((head, para[:cut].strip()))
                para = para[cut:]
            if cur and len(cur) + len(para) > CHUNK_CHARS:
                out.append((head, cur)); cur = ""
            cur = f"{cur}\n\n{para}" if cur else para
        if cur.strip():
            out.append((head, cur.strip()))
    return [(h, t) for h, t in out if t.strip()]


# ---------- indexing ----------

def load_ignores(root: Path) -> list[str]:
    """Source-relative paths (files or folders) listed in <source>/.indexignore."""
    f = root / ".indexignore"
    if not root.is_dir() or not f.is_file():
        return []
    lines = (l.split("#", 1)[0].strip().replace("\\", "/").strip("/") for l in f.read_text(encoding="utf-8").splitlines())
    return [l.lower() for l in lines if l]


def is_ignored(p: Path, root: Path, ignores: list[str] | None = None) -> bool:
    ignores = load_ignores(root) if ignores is None else ignores
    try:
        rel = p.relative_to(root).as_posix().lower()
    except ValueError:
        return False
    return any(rel == ig or rel.startswith(ig + "/") for ig in ignores)


def iter_files(root: Path):
    if root.is_file():
        yield root
        return
    ignores = load_ignores(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not is_ignored(Path(dirpath) / d, root, ignores)
        ]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in EXTENSIONS and not is_ignored(p, root, ignores):
                yield p


def drop_file(con: sqlite3.Connection, file_id: int) -> None:
    ids = [r[0] for r in con.execute("SELECT id FROM chunks WHERE file_id=?", (file_id,))]
    for cid in ids:
        con.execute("DELETE FROM chunks_fts WHERE rowid=?", (cid,))
        con.execute("DELETE FROM chunks_vec WHERE rowid=?", (cid,))
    con.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))
    con.execute("DELETE FROM files WHERE id=?", (file_id,))


def index_file(con: sqlite3.Connection, p: Path, force: bool) -> str:
    key = str(p)
    st = p.stat()
    if st.st_size > MAX_FILE_BYTES:
        return "skipped"
    row = con.execute("SELECT id, mtime, hash FROM files WHERE path=?", (key,)).fetchone()
    if row and not force and abs(row[1] - st.st_mtime) < 1e-6:
        return "unchanged"
    try:
        text = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return "skipped"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if row and not force and row[2] == digest:
        con.execute("UPDATE files SET mtime=? WHERE id=?", (st.st_mtime, row[0]))
        return "unchanged"
    if row:
        drop_file(con, row[0])
    chunks = chunk_text(text, p.suffix.lower() in {".md", ".markdown"})
    cur = con.execute("INSERT INTO files(path, mtime, hash) VALUES(?,?,?)", (key, st.st_mtime, digest))
    file_id = cur.lastrowid
    if chunks:
        vecs = embed([f"{h}\n{t}" if h else t for h, t in chunks])
        for i, ((h, t), v) in enumerate(zip(chunks, vecs)):
            cid = con.execute(
                "INSERT INTO chunks(file_id, ord, heading, text) VALUES(?,?,?,?)", (file_id, i, h, t)
            ).lastrowid
            con.execute("INSERT INTO chunks_fts(rowid, text, heading) VALUES(?,?,?)", (cid, t, h))
            con.execute("INSERT INTO chunks_vec(rowid, embedding) VALUES(?,?)", (cid, v))
    return "updated" if row else "added"


def sync_source(con: sqlite3.Connection, root: Path, force: bool) -> dict:
    stats = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0, "removed": 0}
    seen: set[str] = set()
    for p in iter_files(root):
        seen.add(str(p))
        stats[index_file(con, p, force)] += 1
    prefix = str(root).rstrip("\\/")
    for fid, path in con.execute("SELECT id, path FROM files").fetchall():
        under = path == prefix or path.startswith(prefix + os.sep)
        if under and path not in seen:
            drop_file(con, fid)
            stats["removed"] += 1
    con.commit()
    return stats


# ---------- search ----------

STOPWORDS = frozenset("""
a about after again all am an and any are as at be because been before being both but by can could
did do does doing don't down during each few for from further had has have having he her here hers
him his how i if in into is it its itself just let me more most my no nor not of off on once only or
other our ours out over own same she should so some such than that the their theirs them then there
these they this those through to too under until up very was we were what when where which while who
whom why will with would you your yours
""".split())


def fts_query(q: str) -> str | None:
    toks = re.findall(r"\w+", q)
    content = [t for t in toks if t.lower() not in STOPWORDS] or toks
    return " OR ".join(f'"{t}"' for t in content) if content else None


@mcp.tool()
def index_paths(paths: list[str] | None = None, reindex: bool = False) -> str:
    """Add folders/files to the index (remembered as sources) and sync them.

    With no `paths`, re-syncs every registered source (picks up new, changed and
    deleted files). `reindex=True` forces re-embedding of everything.
    """
    con = db()
    for raw in paths or []:
        p = Path(raw).expanduser().resolve()
        if not p.exists():
            return f"Path does not exist: {p}"
        con.execute("INSERT OR IGNORE INTO sources(path) VALUES(?)", (str(p),))
    con.commit()
    sources = [r[0] for r in con.execute("SELECT path FROM sources ORDER BY path")]
    if not sources:
        return "No sources registered. Call index_paths with one or more paths."
    targets = [str(Path(x).expanduser().resolve()) for x in paths] if paths else sources
    lines = []
    for s in targets:
        lines.append(f"{s}: {sync_source(con, Path(s), reindex)}")
    return "\n".join(lines)


RRF_K = 60


def hybrid_search(
    query: str, limit: int, path_prefix: str | None = None, mode: str = "hybrid"
) -> list[tuple[str, str, str, float]]:
    """Ranked (path, heading, text, score). `mode` is hybrid, fts or vec; the
    single-sided modes exist so eval/run_eval.py can measure each side's contribution."""
    con = db()
    pool = limit * 4
    ranks: dict[int, float] = {}

    fq = fts_query(query)
    if fq and mode in ("hybrid", "fts"):
        for rank, (cid,) in enumerate(
            con.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?", (fq, pool))
        ):
            ranks[cid] = ranks.get(cid, 0) + 1 / (RRF_K + rank)
    if mode in ("hybrid", "vec"):
        qv = embed([query])[0]
        for rank, (cid,) in enumerate(
            con.execute("SELECT rowid FROM chunks_vec WHERE embedding MATCH ? AND k=? ORDER BY distance", (qv, pool))
        ):
            ranks[cid] = ranks.get(cid, 0) + 1 / (RRF_K + rank)

    results = []
    for cid, score in sorted(ranks.items(), key=lambda kv: -kv[1]):
        path, heading, text = con.execute(
            "SELECT f.path, c.heading, c.text FROM chunks c JOIN files f ON f.id=c.file_id WHERE c.id=?", (cid,)
        ).fetchone()
        if path_prefix and not path.lower().startswith(path_prefix.lower()):
            continue
        results.append((path, heading, text, score))
        if len(results) >= limit:
            break
    return results


@mcp.tool()
def search_notes(query: str, limit: int = 8, path_prefix: str | None = None) -> str:
    """Hybrid search (keyword + semantic, merged with reciprocal rank fusion).

    Returns the best-matching chunks with file path and heading. Optionally restrict
    to files whose path starts with `path_prefix`.
    """
    limit = max(1, min(limit, 25))
    results = []
    for i, (path, heading, text, score) in enumerate(hybrid_search(query, limit, path_prefix), 1):
        snippet = text if len(text) <= 700 else text[:700] + "..."
        results.append(f"[{i}] {path}" + (f"  # {heading}" if heading else "") + f"  (score {score:.4f})\n{snippet}")
    return "\n\n".join(results) or "No matches. (Has index_paths been run?)"


@mcp.tool()
def get_note(path: str) -> str:
    """Return the full text of an indexed file (read from disk)."""
    p = Path(path).expanduser().resolve()
    row = db().execute("SELECT 1 FROM files WHERE path=?", (str(p),)).fetchone()
    if not row:
        return f"Not in index: {p}. Only indexed files can be read with this tool."
    return p.read_text(encoding="utf-8")


@mcp.tool()
def list_sources() -> str:
    """List registered source paths with file and chunk counts."""
    con = db()
    out = []
    for (s,) in con.execute("SELECT path FROM sources ORDER BY path").fetchall():
        like = s.rstrip("\\/") + os.sep + "%"
        nf = con.execute("SELECT COUNT(*) FROM files WHERE path=? OR path LIKE ?", (s, like)).fetchone()[0]
        nc = con.execute(
            "SELECT COUNT(*) FROM chunks c JOIN files f ON f.id=c.file_id WHERE f.path=? OR f.path LIKE ?", (s, like)
        ).fetchone()[0]
        out.append(f"{s}: {nf} files, {nc} chunks")
    return "\n".join(out) or "No sources registered."


@mcp.tool()
def remove_source(path: str) -> str:
    """Unregister a source and delete its files/chunks from the index (files on disk are untouched)."""
    con = db()
    s = str(Path(path).expanduser().resolve())
    con.execute("DELETE FROM sources WHERE path=?", (s,))
    like = s.rstrip("\\/") + os.sep + "%"
    ids = [r[0] for r in con.execute("SELECT id FROM files WHERE path=? OR path LIKE ?", (s, like))]
    for fid in ids:
        drop_file(con, fid)
    con.commit()
    return f"Removed {s} ({len(ids)} files dropped from index)."


if __name__ == "__main__":
    mcp.run()

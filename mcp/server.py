"""Vault index MCP server: hybrid keyword (FTS5) + vector (sqlite-vec) search.

Embeddings come from fastembed (ONNX, CPU). Everything lives in one SQLite file.
Env:
  VAULT_INDEX_DB     path to the SQLite file (default ~/.mcp-memory/vault-index.db)
  VAULT_MODEL_CACHE  fastembed model cache dir (default ~/.mcp-memory/models)
  VAULT_RERANK       0 turns off the cross-encoder rerank of the top results (default 1)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

import sqlite_vec
from mcp.server.fastmcp import FastMCP

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIM = 384
# Cross-encoder that reorders the top fused candidates (docs/adr/2026-10-24-cross-encoder-rerank.md).
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
RERANK_N = 10
RERANK = os.environ.get("VAULT_RERANK", "1") != "0"
# Two ONNX sessions with a thread per core fight each other: interleaved embed + rerank went from
# about 170 ms to 510 ms on 24 cores. Capping each keeps a search near 190 ms.
THREADS = max(1, min(8, (os.cpu_count() or 2) // 2))
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
_reranker = None
_db: sqlite3.Connection | None = None


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load_model(kind, name: str, size: str):
    MODEL_CACHE.mkdir(parents=True, exist_ok=True)
    try:
        return kind(name, cache_dir=str(MODEL_CACHE), threads=THREADS)
    except Exception as e:
        raise RuntimeError(
            f"Could not load model {name} into {MODEL_CACHE}: {e}. "
            f"The first run downloads it (about {size}) and needs internet; set VAULT_MODEL_CACHE to move it."
        ) from e


def embedder():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding

        _embedder = load_model(TextEmbedding, MODEL_NAME, "65 MB")
    return _embedder


def reranker():
    global _reranker
    if _reranker is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        _reranker = load_model(TextCrossEncoder, RERANK_MODEL, "80 MB")
    return _reranker


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
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        # Indexes from before the meta table were all built with the current model.
        con.execute("INSERT OR IGNORE INTO meta VALUES('model', ?)", (f"{MODEL_NAME} ({DIM})",))
        con.commit()
        _db = con
    return _db


def model_mismatch(con: sqlite3.Connection) -> str | None:
    """An explanation if the index was built with another embedding model, else None."""
    built = con.execute("SELECT value FROM meta WHERE key='model'").fetchone()[0]
    want = f"{MODEL_NAME} ({DIM})"
    if built == want:
        return None
    return f"The index was built with {built}, but this server uses {want}. Run index_paths with reindex=True."


def rebuild_for_model(con: sqlite3.Connection) -> None:
    """Empty the index and recreate the vector table for the current model (reindex=True after a model change)."""
    con.executescript(f"""
        DELETE FROM chunks; DELETE FROM chunks_fts; DELETE FROM files;
        DROP TABLE chunks_vec;
        CREATE VIRTUAL TABLE chunks_vec USING vec0(embedding float[{DIM}]);
    """)
    con.execute("UPDATE meta SET value=? WHERE key='model'", (f"{MODEL_NAME} ({DIM})",))
    con.commit()


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
                    out.append((head, cur))
                    cur = ""
                out.append((head, para[:cut].strip()))
                para = para[cut:]
            if cur and len(cur) + len(para) > CHUNK_CHARS:
                out.append((head, cur))
                cur = ""
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
    try:
        st = p.stat()
    except FileNotFoundError:  # deleted between the folder walk and now (editor temp files)
        return "vanished"
    row = con.execute("SELECT id, mtime, hash FROM files WHERE path=?", (key,)).fetchone()
    if row and not force and abs(row[1] - st.st_mtime) < 1e-6:
        return "unchanged"
    try:
        text = p.read_text(encoding="utf-8") if st.st_size <= MAX_FILE_BYTES else None
    except (UnicodeDecodeError, OSError):
        text = None
    if text is None:  # too big or unreadable now: never keep serving its old chunks
        if row:
            drop_file(con, row[0])
        return "skipped"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if row and not force and row[2] == digest:
        con.execute("UPDATE files SET mtime=? WHERE id=?", (st.st_mtime, row[0]))
        return "unchanged"
    chunks = chunk_text(text, p.suffix.lower() in {".md", ".markdown"})
    # Embed before touching the index, so a failure leaves the old version in place.
    vecs = embed([f"{h}\n{t}" if h else t for h, t in chunks]) if chunks else []
    if row:
        drop_file(con, row[0])
    cur = con.execute("INSERT INTO files(path, mtime, hash) VALUES(?,?,?)", (key, st.st_mtime, digest))
    file_id = cur.lastrowid
    if chunks:
        for i, ((h, t), v) in enumerate(zip(chunks, vecs, strict=True)):
            cid = con.execute(
                "INSERT INTO chunks(file_id, ord, heading, text) VALUES(?,?,?,?)", (file_id, i, h, t)
            ).lastrowid
            con.execute("INSERT INTO chunks_fts(rowid, text, heading) VALUES(?,?,?)", (cid, t, h))
            con.execute("INSERT INTO chunks_vec(rowid, embedding) VALUES(?,?)", (cid, v))
    return "updated" if row else "added"


def sync_source(con: sqlite3.Connection, root: Path, force: bool) -> dict:
    """Index new and changed files under `root` and drop deleted ones. Commits per file, so
    a failure keeps the files done so far and other writers (the hook) never wait long."""
    stats = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0, "removed": 0}
    seen: set[str] = set()
    try:
        for p in iter_files(root):
            result = index_file(con, p, force)
            if result == "vanished":
                continue  # not seen, so the removal pass drops any old copy
            seen.add(str(p))
            stats[result] += 1
            con.commit()
            if result in ("added", "updated") and (stats["added"] + stats["updated"]) % 50 == 0:
                log(f"vault-index: {stats['added'] + stats['updated']} files embedded so far in {root}")
        for fid, path in files_under(con, str(root)):
            if path not in seen:
                drop_file(con, fid)
                stats["removed"] += 1
    except BaseException:
        con.rollback()  # the connection is long-lived; a later commit must never keep half a file
        raise
    con.commit()
    return stats


def files_under(con: sqlite3.Connection, source: str) -> list[tuple[int, str]]:
    """(id, path) of indexed files at or below `source`. A plain string match: LIKE treats _ and % as wildcards."""
    prefix = source.rstrip("\\/")
    return [(fid, path) for fid, path in con.execute("SELECT id, path FROM files").fetchall()
            if path == prefix or path.startswith(prefix + os.sep)]


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
    deleted files). `reindex=True` forces re-embedding of everything (needed after a model change).
    A registered source that is missing on disk keeps its index until remove_source.
    """
    con = db()
    if reindex and model_mismatch(con):
        rebuild_for_model(con)
    elif problem := model_mismatch(con):
        return problem
    resolved = [Path(raw).expanduser().resolve() for raw in paths or []]
    missing = [str(p) for p in resolved if not p.exists()]
    if missing:  # check all before writing anything
        return "Path does not exist: " + ", ".join(missing)
    for p in resolved:
        con.execute("INSERT OR IGNORE INTO sources(path) VALUES(?)", (str(p),))
    con.commit()
    sources = [r[0] for r in con.execute("SELECT path FROM sources ORDER BY path")]
    if not sources:
        return "No sources registered. Call index_paths with one or more paths."
    lines = []
    for s in [str(p) for p in resolved] or sources:
        if not Path(s).exists():  # e.g. an unplugged drive: dropping its index would force a full re-embed later
            lines.append(f"{s}: missing on disk; index kept (remove_source drops it)")
            continue
        lines.append(f"{s}: {sync_source(con, Path(s), reindex)}")
    return "\n".join(lines)


RRF_K = 60
# Keyword ranks count at a tenth of vector ranks: a tie-breaker and jargon booster, not an equal vote.
# Beat equal weights on both golden sets (docs/adr/2026-10-23-fts-weight-in-fusion.md).
FTS_WEIGHT = 0.1


def hybrid_search(
    query: str, limit: int, path_prefix: str | None = None, mode: str = "hybrid"
) -> list[tuple[str, str, str, float]]:
    """Ranked (path, heading, text, score). `mode` is hybrid (fusion, then the cross-encoder
    reorders the top max(limit, RERANK_N) unless VAULT_RERANK=0), fused (fusion only), fts or vec;
    the other modes exist so eval/run_eval.py can measure each stage's contribution."""
    rerank = mode == "hybrid" and RERANK
    final = limit
    if rerank:
        limit = max(limit, RERANK_N)
    if mode == "fused":
        mode = "hybrid"
    con = db()
    pool = limit * 4
    ranks: dict[int, float] = {}
    # With a prefix, both sides rank only chunks under it, so a filtered search never comes back
    # short just because other folders filled the candidate pool.
    scope = json.dumps(prefix_chunk_ids(con, path_prefix)) if path_prefix else None

    fq = fts_query(query)
    if fq and mode in ("hybrid", "fts"):
        sql = "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?"
        args: tuple = (fq,)
        if scope:
            sql, args = sql + " AND rowid IN (SELECT value FROM json_each(?))", (fq, scope)
        for rank, (cid,) in enumerate(con.execute(sql + " ORDER BY bm25(chunks_fts) LIMIT ?", (*args, pool))):
            ranks[cid] = ranks.get(cid, 0) + (FTS_WEIGHT if mode == "hybrid" else 1) / (RRF_K + rank)
    if mode in ("hybrid", "vec"):
        qv = embed([query])[0]
        if scope:  # exact distances over the scoped chunks (vec0's kNN index cannot filter by path)
            rows = con.execute(
                "SELECT rowid FROM chunks_vec WHERE rowid IN (SELECT value FROM json_each(?))"
                " ORDER BY vec_distance_l2(embedding, ?) LIMIT ?", (scope, qv, pool))
        else:
            rows = con.execute("SELECT rowid FROM chunks_vec WHERE embedding MATCH ? AND k=? ORDER BY distance", (qv, pool))
        for rank, (cid,) in enumerate(rows):
            ranks[cid] = ranks.get(cid, 0) + 1 / (RRF_K + rank)

    results = []
    for cid, score in sorted(ranks.items(), key=lambda kv: -kv[1])[:limit]:
        path, heading, text = con.execute(
            "SELECT f.path, c.heading, c.text FROM chunks c JOIN files f ON f.id=c.file_id WHERE c.id=?", (cid,)
        ).fetchone()
        results.append((path, heading, text, score))
    if rerank and results:
        try:
            model = reranker()
        except RuntimeError as e:  # e.g. offline before the reranker was ever downloaded: serve fusion order
            log(f"vault-index: rerank skipped: {e}")
        else:
            scores = list(model.rerank(query, [f"{h}\n{t}" if h else t for _, h, t, _ in results]))
            order = sorted(range(len(results)), key=lambda i: -scores[i])
            results = [(*results[i][:3], float(scores[i])) for i in order]
    return results[:final]


def prefix_chunk_ids(con: sqlite3.Connection, path_prefix: str) -> list[int]:
    """Ids of chunks whose file path starts with `path_prefix`: an absolute path, or one relative
    to any registered source (e.g. "docs/lessons.md"). Case-insensitive; / and \\ are the same."""
    def norm(s: str) -> str:
        return s.replace("\\", "/").lower()

    p = Path(path_prefix).expanduser()
    if p.is_absolute():
        bases = [norm(str(p))]
    else:
        rel = norm(path_prefix).removeprefix("./")
        bases = [norm(s).rstrip("/") + "/" + rel for (s,) in con.execute("SELECT path FROM sources")]
    rows = con.execute("SELECT c.id, f.path FROM chunks c JOIN files f ON f.id=c.file_id")
    return [cid for cid, path in rows if norm(path).startswith(tuple(bases))]


@mcp.tool()
def search_notes(query: str, limit: int = 8, path_prefix: str | None = None) -> str:
    """Hybrid search (keyword + semantic, merged with reciprocal rank fusion, then the top
    results reordered by a cross-encoder).

    Returns the best-matching chunks with file path, heading and score (higher is better). `path_prefix` restricts
    the search to files under it: an absolute path, or one relative to a source such as
    "docs/lessons.md" (either slash, any case).
    """
    limit = max(1, min(limit, 25))
    if problem := model_mismatch(db()):
        return problem
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
    if not p.is_file():
        return f"{p} is indexed but no longer on disk. Run index_paths to sync."
    return p.read_text(encoding="utf-8")


@mcp.tool()
def list_sources() -> str:
    """List registered source paths with file and chunk counts."""
    con = db()
    counts = con.execute(
        "SELECT f.path, COUNT(c.id) FROM files f LEFT JOIN chunks c ON c.file_id=f.id GROUP BY f.id").fetchall()
    out = []
    for (s,) in con.execute("SELECT path FROM sources ORDER BY path").fetchall():
        prefix = s.rstrip("\\/")
        mine = [n for path, n in counts if path == prefix or path.startswith(prefix + os.sep)]
        out.append(f"{s}: {len(mine)} files, {sum(mine)} chunks")
    return "\n".join(out) or "No sources registered."


@mcp.tool()
def remove_source(path: str) -> str:
    """Unregister a source and delete its files/chunks from the index (files on disk are untouched)."""
    con = db()
    s = str(Path(path).expanduser().resolve())
    con.execute("DELETE FROM sources WHERE path=?", (s,))
    ids = [fid for fid, _ in files_under(con, s)]
    for fid in ids:
        drop_file(con, fid)
    con.commit()
    return f"Removed {s} ({len(ids)} files dropped from index)."


def version() -> str:
    try:
        from importlib.metadata import version as dist_version

        return dist_version("vault-index")
    except Exception:  # running from a source checkout, not an installed package
        return "source"


def main(argv: list[str] | None = None) -> None:
    """Console entry point (`uvx vault-index`). No command serves MCP over stdio."""
    import argparse

    ap = argparse.ArgumentParser(
        prog="vault-index",
        description="Local hybrid (FTS5 + sqlite-vec) search over markdown and code. "
                    "With no command, serves MCP over stdio for Claude Code and other MCP clients.",
        epilog=f"Index: {DB_PATH} (VAULT_INDEX_DB). Model cache: {MODEL_CACHE} (VAULT_MODEL_CACHE). "
               "VAULT_RERANK=0 turns off the rerank.",
    )
    ap.add_argument("--version", action="version", version=f"vault-index {version()}")
    sub = ap.add_subparsers(dest="cmd")
    ix = sub.add_parser("index", help="index folders or files (remembered as sources); no paths re-syncs all")
    ix.add_argument("paths", nargs="*")
    ix.add_argument("--reindex", action="store_true", help="re-embed everything (needed after a model change)")
    se = sub.add_parser("search", help="search the index from the terminal")
    se.add_argument("query")
    se.add_argument("-n", "--limit", type=int, default=8)
    se.add_argument("--path-prefix", help="only files under this path (absolute or relative to a source)")
    sub.add_parser("sources", help="list sources with file and chunk counts")
    sub.add_parser("serve", help="serve MCP over stdio (the default)")
    args = ap.parse_args(argv)

    if args.cmd == "index":
        print(index_paths(args.paths or None, args.reindex))
        if RERANK:  # download it now, not inside the first search
            reranker()
    elif args.cmd == "search":
        print(search_notes(args.query, args.limit, args.path_prefix))
    elif args.cmd == "sources":
        print(list_sources())
    else:
        if sys.stdin.isatty():
            log("vault-index: serving MCP over stdio (start it from an MCP client; see vault-index --help)")
        mcp.run()


if __name__ == "__main__":
    main()

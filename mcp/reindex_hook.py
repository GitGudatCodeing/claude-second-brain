"""Claude Code hook that keeps the vault index in sync.

PostToolUse (Write/Edit): re-index the edited file, if it is an indexable type under a registered source.
Stop (async): re-sync every source, which catches what the PostToolUse path cannot see: edits made from
the shell or by scripts, git checkouts and deleted files. Unchanged files cost a hash check only.
Reads the hook JSON from stdin. Always exits 0 so it never blocks the session.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

LOG_NAME = "reindex-hook.log"
LOG_MAX_LINES = 200  # past this, keep the last LOG_KEEP_LINES
LOG_KEEP_LINES = 100


def load_server():
    try:
        import server
    except ImportError:  # run by the plugin with the published package (uvx --from vault-index)
        import vault_index as server
    return server


def log_failure(event: str, exc: Exception) -> None:
    """Append one line to reindex-hook.log next to the index DB, so a broken hook is visible. Never raises."""
    try:
        try:
            folder = load_server().DB_PATH.parent
        except Exception:
            folder = Path.home() / ".mcp-memory"
        path = folder / LOG_NAME
        msg = " ".join(f"{type(exc).__name__}: {exc}".split())
        line = f"{datetime.now().isoformat(timespec='seconds')} {event or '-'} {msg}"
        folder.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="") as f:
            f.write(line + "\n")
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > LOG_MAX_LINES:
            path.write_text("\n".join(lines[-LOG_KEEP_LINES:]) + "\n", encoding="utf-8", newline="")
    except Exception:
        pass


def main() -> None:
    event = ""
    try:
        data = json.load(sys.stdin)
        event = str(data.get("hook_event_name") or "PostToolUse")
        if data.get("hook_event_name") == "Stop":
            load_server().index_paths()  # quiet: stdout of an async hook would reach the model
            return
        raw = (data.get("tool_input") or {}).get("file_path")
        if not raw:
            return
        p = Path(raw).resolve()

        server = load_server()  # heavy import, only after cheap checks

        if p.suffix.lower() not in server.EXTENSIONS or not p.is_file():
            return
        con = server.db()
        sources = [r[0] for r in con.execute("SELECT path FROM sources")]
        owner = next((s for s in sources if str(p) == s or str(p).startswith(s.rstrip("\\/") + os.sep)), None)
        if owner is None or server.is_ignored(p, Path(owner)):
            return
        # Like iter_files: skip folders below the source only, so a vault under e.g. ~/build still works.
        if any(part in server.SKIP_DIRS for part in p.relative_to(owner).parts[:-1]):
            return
        result = server.index_file(con, p, force=False)
        con.commit()
        print(f"vault-index: {p.name} {result}", file=sys.stderr)
    except Exception as e:  # never break the editing flow
        print(f"vault-index hook error: {e}", file=sys.stderr)
        log_failure(event, e)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()

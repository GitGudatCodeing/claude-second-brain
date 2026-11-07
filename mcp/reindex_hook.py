"""Claude Code hook that keeps the vault index in sync.

PostToolUse (Write/Edit): re-index the edited file, if it is an indexable type under a registered source.
Stop (async): re-sync every source, which catches what the PostToolUse path cannot see: edits made from
the shell or by scripts, git checkouts and deleted files. Unchanged files cost a hash check only.
Reads the hook JSON from stdin. Always exits 0 so it never blocks the session.
"""
import json
import os
import sys
from pathlib import Path


def load_server():
    try:
        import server
    except ImportError:  # run by the plugin with the published package (uvx --from vault-index)
        import vault_index as server
    return server


def main() -> None:
    try:
        data = json.load(sys.stdin)
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


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()

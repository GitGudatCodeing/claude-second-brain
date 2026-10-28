"""Claude Code PostToolUse hook: re-index a file after Write/Edit.

Reads the hook JSON from stdin. Does nothing unless the edited file is an indexable
type under a registered source. Always exits 0 so it never blocks the session.
"""
import json
import os
import sys
from pathlib import Path


def main() -> None:
    try:
        data = json.load(sys.stdin)
        raw = (data.get("tool_input") or {}).get("file_path")
        if not raw:
            return
        p = Path(raw).resolve()

        try:  # heavy import, only after cheap checks
            import server
        except ImportError:  # run by the plugin with the published package (uvx --from vault-index)
            import vault_index as server

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

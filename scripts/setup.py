"""One-command setup for a fresh clone.

  uv run --project mcp python scripts/setup.py [--memory-file PATH] [--force]

1. Checks that uv and npx are on PATH (npx runs the memory graph server).
2. Writes .mcp.json from .mcp.json.example with an absolute memory file path
   (default ~/.mcp-memory/memory.jsonl). Keeps an existing .mcp.json unless --force.
3. Indexes this folder (the first run downloads the embedding model, about 130 MB).
4. Runs the invariants and prints what to do next.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def step(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--memory-file", default=str(Path.home() / ".mcp-memory" / "memory.jsonl"))
    ap.add_argument("--force", action="store_true", help="overwrite an existing .mcp.json")
    args = ap.parse_args()

    step("Checking tools")
    missing = [t for t in ("uv", "npx") if not shutil.which(t)]
    for t in missing:
        print(f"  missing: {t} ({'https://docs.astral.sh/uv/' if t == 'uv' else 'install Node.js'})")
    if "uv" in missing:
        return 1
    print("  ok" if not missing else "  continuing; the memory graph server needs npx")

    step("Writing .mcp.json")
    cfg_path = ROOT / ".mcp.json"
    if cfg_path.exists() and not args.force:
        print(f"  kept existing {cfg_path.name} (use --force to rewrite)")
    else:
        cfg = json.loads((ROOT / ".mcp.json.example").read_text(encoding="utf-8"))
        mem = Path(args.memory_file).expanduser().resolve()
        mem.parent.mkdir(parents=True, exist_ok=True)
        cfg["mcpServers"]["memory"]["env"]["MEMORY_FILE_PATH"] = mem.as_posix()
        cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        print(f"  memory graph file: {mem}")

    step("Indexing this folder (first run downloads the embedding model)")
    sys.path.insert(0, str(ROOT / "mcp"))
    import server

    print("  " + server.index_paths([str(ROOT)]))

    step("Checking the wiring")
    code = subprocess.run([sys.executable, str(ROOT / "scripts" / "invariants.py")], check=False).returncode

    step("Next")
    print("  1. Start `claude` in this folder and approve the project MCP servers and hooks.")
    print("  2. Try: /recall garden sensor battery life")
    print("  3. Put your own notes in notes/; delete example-vault/ when you no longer need the eval.")
    return code


if __name__ == "__main__":
    sys.exit(main())

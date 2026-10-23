"""Compare vault-index with basic-memory (https://github.com/basicmachines-co/basic-memory) on eval/golden.jsonl.

basic-memory returns whole notes, so both systems are scored per file here: each golden
label counts for its file (best grade per file), and vault-index chunks are collapsed to
their first-ranked file. basic-memory runs on a scratch copy of the same markdown files
(it rewrites frontmatter), with its own config dir, its default search (hybrid) and the
same embedding model (fastembed bge-small-en-v1.5). Needs uv; not part of CI.

  uv run --project mcp python eval/compare_basic_memory.py [-v]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import run_eval
from run_eval import METRICS, ROOT, K, score, server

BM_VERSION = "0.24.1"
FILE_POOL = 25  # vault-index chunks fetched before collapsing to files, so it can fill K distinct files


def bm(args: list[str], env: dict) -> str:
    cmd = ["uvx", "--python", "3.12", f"basic-memory@{BM_VERSION}", *args]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(f"basic-memory {' '.join(args[:2])} failed ({r.returncode}):\n{r.stderr.strip()}")
    return r.stdout


def file_labels(q: dict) -> dict:
    best: dict[str, int] = {}
    for lab in q["relevant"]:
        best[lab["path"]] = max(best.get(lab["path"], 0), lab["grade"])
    return {**q, "relevant": [{"path": p, "heading": "", "grade": g} for p, g in best.items()]}


def first_per_file(results) -> list[tuple[str, str, str, float]]:
    seen, out = set(), []
    for path, _, _, s in results:
        if path.lower() not in seen:
            seen.add(path.lower())
            out.append((path, "", "", s))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--bm-mode", choices=["default", "vector"], default="default",
                    help="basic-memory search: its default (hybrid) or --vector")
    args = ap.parse_args()

    fresh = not server.db().execute("SELECT 1 FROM sources").fetchone()
    print(f"syncing index: {server.index_paths([str(ROOT)] if fresh else None)}")
    golden = [file_labels(q) for q in run_eval.load_golden()]

    scratch = Path(tempfile.mkdtemp(prefix="bm-eval-"))
    try:
        corpus = scratch / "corpus"
        n = 0
        for p in server.iter_files(ROOT):  # the files vault-index indexes; basic-memory reads markdown
            if p.suffix.lower() in {".md", ".markdown"}:
                dst = corpus / p.relative_to(ROOT)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, dst)
                n += 1
        env = {**os.environ, "BASIC_MEMORY_CONFIG_DIR": str(scratch / "config")}
        bm(["project", "add", "eval", str(corpus), "--default"], env)
        bm(["reindex"], env)
        print(f"basic-memory {BM_VERSION}: indexed a copy of {n} markdown files")

        systems = {"vault-index hybrid": {m: 0.0 for m in METRICS}, f"basic-memory {BM_VERSION}": {m: 0.0 for m in METRICS}}
        for q in golden:
            vi = first_per_file(server.hybrid_search(q["q"], FILE_POOL))
            flags = {"default": [], "vector": ["--vector"]}[args.bm_mode]
            cmd = ["tool", "search-notes", q["q"], "--json", "--page-size", str(K * 2), "--project", "eval", *flags]
            out = json.loads(bm(cmd, env))
            bmr = [(str(ROOT / r["file_path"]), "", "", float(r.get("score") or 0))
                   for r in out.get("results", []) if r.get("file_path")]
            for name, res in zip(systems, (vi, first_per_file(bmr)), strict=True):
                s, _ = score(q, res)
                for m in METRICS:
                    systems[name][m] += s[m] / len(golden)
                if args.verbose:
                    print(f"  {q['id']} {name:22} ndcg={s['ndcg@5']:.2f}  top: {[Path(p).name for p, *_ in res[:K]]}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    print(f"\n{len(golden)} questions, file-level, K={K}")
    print(f"{'system':24}" + "".join(f"{m:>10}" for m in METRICS))
    for name, s in systems.items():
        print(f"{name:24}" + "".join(f"{s[m]:10.3f}" for m in METRICS))
    return 0


if __name__ == "__main__":
    sys.exit(main())

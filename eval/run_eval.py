"""Retrieval eval against eval/golden.jsonl.

Scores exactly what search_notes serves: server.hybrid_search with the tool's
default limit (so the fusion depth matches production), cut at K for metrics.

  uv run --project mcp python eval/run_eval.py                 hybrid vs baseline
  uv run --project mcp python eval/run_eval.py --modes all     also fused (no rerank), fts, vec and a grep baseline
  uv run --project mcp python eval/run_eval.py -v              per-question detail
  uv run --project mcp python eval/run_eval.py --save-baseline record current hybrid scores

Exit 1 if any hybrid metric drops more than MAX_DROP below the saved baseline.

With an empty index (no sources yet), this folder is registered and indexed first.
Set VAULT_INDEX_DB to a scratch file to keep the eval away from your real index.

Golden labels: {"path": relative to SecondBrain, "heading": substring of the chunk
heading ("" = any chunk of the file), "grade": 2 highly relevant, 1 partly}.
A label counts once, at the rank of its first matching chunk.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp"))
import server  # noqa: E402

GOLDEN = ROOT / "eval" / "golden.jsonl"
BASELINE = ROOT / "eval" / "baseline.json"
K = 5
SERVED_LIMIT = 8  # search_notes default; determines the fusion pool size
MAX_DROP = 0.03
METRICS = ("ndcg@5", "mrr", "recall@5")


def golden_sha256(path: Path = GOLDEN) -> str:
    """Hash of the golden file with line endings normalised, so CRLF vs LF does not change it."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def baseline_notes(base: dict, golden_hash: str, model: str, scores: dict) -> list[str]:
    """Warnings and hints from comparing the saved baseline with the current golden set, model and scores."""
    out = []
    saved = base.get("golden_sha256")
    if saved and saved != golden_hash:
        out.append(f"WARNING: baseline is stale: golden set changed since {base.get('date')}; re-save with --save-baseline")
    elif not saved:
        out.append("hint: baseline has no golden_sha256; re-save with --save-baseline to track golden changes")
    if base.get("model") and base["model"] != model:
        out.append(f"WARNING: baseline model was {base['model']}, now {model}")
    risen = [m for m in METRICS if scores[m] > base["scores"][m] + MAX_DROP]
    if risen:
        out.append(f"hint: {', '.join(risen)} rose more than {MAX_DROP}; the baseline can be re-saved with --save-baseline")
    return out


def question_moves(base: dict, current: dict, texts: dict) -> list[str]:
    """Lines for questions whose ndcg moved against the baseline's per_question; a hint if it has none."""
    old = base.get("per_question")
    if old is None:
        return ["hint: baseline has no per_question; re-save with --save-baseline to see which questions moved"]
    out = []
    for qid in sorted(set(old) | set(current)):
        text = texts.get(qid, "")
        text = text if len(text) <= 60 else text[:57] + "..."
        if qid not in old:
            out.append(f"  {qid} new  ndcg {current[qid]['ndcg@5']:.3f}  {text}")
        elif qid not in current:
            out.append(f"  {qid} removed  (was ndcg {old[qid]['ndcg@5']:.3f})")
        elif abs(current[qid]["ndcg@5"] - old[qid]["ndcg@5"]) > 0.001:
            out.append(f"  {qid} ndcg {old[qid]['ndcg@5']:.3f} -> {current[qid]['ndcg@5']:.3f}  {text}")
    return out


def load_golden() -> list[dict]:
    return [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]


def label_rank(label: dict, results: list[tuple[str, str, str, float]]) -> int | None:
    want = str((ROOT / label["path"]).resolve()).lower()
    for i, (path, heading, _, _) in enumerate(results):
        if path.lower() == want and label["heading"].lower() in heading.lower():
            return i
    return None


def score(q: dict, results) -> tuple[dict, list]:
    top = results[:K]
    # Credit each rank position to at most one label (the highest grade matching it).
    gains = [0] * K
    found = []
    for lab in sorted(q["relevant"], key=lambda l: -l["grade"]):
        r = label_rank(lab, top)
        if r is not None and gains[r] == 0:
            gains[r] = lab["grade"]
            found.append((lab, r))
    dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted((l["grade"] for l in q["relevant"]), reverse=True)[:K]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    first = min((r for _, r in found), default=None)
    return {
        "ndcg@5": dcg / idcg if idcg else 0.0,
        "mrr": 1 / (first + 1) if first is not None else 0.0,
        "recall@5": len(found) / len(q["relevant"]),
    }, found


def grep_search(query: str, limit: int) -> list[tuple[str, str, str, float]]:
    """Comparison baseline with no index: rank chunks by how many query words they contain
    (case-insensitive substring, like a grep per word), then by total occurrences."""
    words = [w for w in (t.lower() for t in re.findall(r"\w+", query)) if w not in server.STOPWORDS]
    rows = server.db().execute("SELECT f.path, c.heading, c.text FROM chunks c JOIN files f ON f.id=c.file_id")
    scored = []
    for path, heading, text in rows:
        low = f"{heading}\n{text}".lower()
        hits = sum(1 for w in words if w in low)
        if hits:
            scored.append((hits, sum(low.count(w) for w in words), path, heading, text))
    scored.sort(key=lambda s: (-s[0], -s[1], s[2].replace("\\", "/").lower(), s[3]))  # ties: path, heading (same on any OS)
    return [(p, h, t, float(n)) for n, _, p, h, t in scored[:limit]]


def run(mode: str, golden: list[dict], verbose: bool) -> tuple[dict, dict]:
    """Mean scores, and each question id mapped to its scores (rounded to 4 decimals)."""
    per_q = []
    by_id = {}
    for q in golden:
        if mode == "grep":
            results = grep_search(q["q"], SERVED_LIMIT)
        else:
            results = server.hybrid_search(q["q"], SERVED_LIMIT, mode=mode)
        s, found = score(q, results)
        per_q.append(s)
        by_id[q["id"]] = {m: round(s[m], 4) for m in METRICS}
        if verbose:
            print(f"  {q['id']} ndcg={s['ndcg@5']:.2f} mrr={s['mrr']:.2f} recall={s['recall@5']:.2f}  {q['q']}")
            if s["recall@5"] < 1:
                got = [f"{Path(p).name}#{h.split(' > ')[-1][:30]}" for p, h, _, _ in results[:K]]
                print(f"      top{K}: {got}")
    return {m: sum(s[m] for s in per_q) / len(per_q) for m in METRICS}, by_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="hybrid", help="hybrid, or 'all' (adds fused, fts, vec, grep)")
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--model", help="evaluate another fastembed model in a separate scratch index "
                                    "(production index untouched; cannot be combined with --save-baseline)")
    args = ap.parse_args()

    if args.model:
        if args.save_baseline:
            ap.error("--model is for comparison only; switch server.MODEL_NAME and reindex to adopt a model")
        slug = re.sub(r"[^a-z0-9]+", "-", args.model.lower()).strip("-")
        server.MODEL_NAME = args.model
        server.DB_PATH = server.HOME / f"eval-{slug}.db"
        server._db = server._embedder = None
        dim = len(next(iter(server.embedder().embed(["probe"]))))
        server.DIM = dim  # the scratch index gets its own schema; adopting a new size needs a reindex
        print(f"scratch index {server.DB_PATH}: {server.index_paths([str(ROOT)])}")
    else:
        fresh = not server.db().execute("SELECT 1 FROM sources").fetchone()  # e.g. a new clone or CI
        print(f"syncing index: {server.index_paths([str(ROOT)] if fresh else None)}")
    golden = load_golden()
    modes = ["hybrid", "fused", "fts", "vec", "grep"] if args.modes == "all" else ["hybrid"]
    scores = {}
    per_question = {}
    for mode in modes:
        if args.verbose:
            print(f"\n[{mode}]")
        scores[mode], per_question[mode] = run(mode, golden, args.verbose)

    print(f"\n{len(golden)} questions, K={K}, model={server.MODEL_NAME}")
    print(f"{'mode':8}" + "".join(f"{m:>10}" for m in METRICS))
    for mode, s in scores.items():
        print(f"{mode:8}" + "".join(f"{s[m]:10.3f}" for m in METRICS))

    hybrid = scores["hybrid"]
    if args.save_baseline:
        BASELINE.write_text(json.dumps({
            "date": dt.date.today().isoformat(), "model": server.MODEL_NAME,
            "questions": len(golden), "golden_sha256": golden_sha256(), "scores": hybrid,
            "per_question": per_question["hybrid"],
        }, indent=2) + "\n", encoding="utf-8")
        print(f"\nbaseline saved to {BASELINE.relative_to(ROOT)}")
        return 0
    if not BASELINE.exists():
        print("\nno baseline yet; run with --save-baseline")
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    if base["questions"] != len(golden):
        print(f"\nnote: baseline had {base['questions']} questions, now {len(golden)}; re-save the baseline")
    for note in baseline_notes(base, golden_sha256(), server.MODEL_NAME, hybrid):
        print(f"\n{note}")
    drops = [m for m in METRICS if hybrid[m] < base["scores"][m] - MAX_DROP]
    print(f"\nvs baseline {base['date']}: " + ", ".join(
        f"{m} {hybrid[m] - base['scores'][m]:+.3f}" for m in METRICS))
    moves = question_moves(base, per_question["hybrid"], {q["id"]: q["q"] for q in golden})
    if moves:
        print("\n".join(moves))
    if drops:
        print(f"REGRESSION (> {MAX_DROP} drop): {', '.join(drops)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

---
status: accepted
date: 2026-10-20
entities: [vault-index-server, adr-2026-10-20-hybrid-sqlite-vec-vault-index]
---

# ADR: Search tuning round 1 (index scope, stopwords, embedding model)

## Context
The first golden-set eval (`eval/golden.jsonl`, 15 starter questions written by Claude, paraphrased on purpose) showed tooling code (`mcp/`, `scripts/`, `eval/`) taking top-5 slots in most misses, and the keyword side adding noise by matching stopwords. The pack's lessons also claimed MiniLM beat bge-small in hybrid search. Each change was tested alone against the saved baseline (hybrid scores, K=5, max allowed drop 0.03).

## Decision
- Keep: exclude tooling code via a per-source `.indexignore` (`mcp`, `scripts`, `eval`).
- Keep: drop English stopwords from the FTS query, falling back to all tokens.
- Reject: switching embeddings to all-MiniLM-L6-v2; stay on BAAI/bge-small-en-v1.5.

## Options considered
| Experiment | NDCG@5 | MRR | Recall@5 | Result |
|---|---|---|---|---|
| Control (code labels removed from q06, q11) | 0.574 | 0.633 | 0.600 | re-run reproduced exactly |
| 1. `.indexignore` for tooling code | 0.637 (+0.063) | 0.717 (+0.083) | 0.667 (+0.067) | kept |
| 2. FTS stopword removal | 0.655 (+0.018) | 0.706 (-0.011) | 0.733 (+0.067) | kept |
| 3. MiniLM-L6-v2 embeddings | 0.630 (-0.024) | 0.680 (-0.026) | 0.667 (-0.067) | rejected |

The scratch-index pipeline used for experiment 3 was validated by a control run with bge-small, which reproduced the baseline exactly.

## Consequences
- Current baseline: NDCG@5 0.655, MRR 0.706, Recall@5 0.733 (`eval/baseline.json`).
- With 15 questions, one question is worth 0.067 recall; experiment 2's gain is about one question and should be re-checked once real questions replace the starter set.
- After experiment 2, vector-only (0.656 NDCG) still roughly matches hybrid; revisit fusion weighting once the golden set includes jargon-heavy questions, where keywords should help.
- Running MCP server processes started before this change still use the old code (no `.indexignore`, no stopwords) until restarted.

## Update (same day, after the vault existed)
Golden set grown from 15 to 23 questions, 8 of them about real vault notes (goals, email system, preferences, lessons). New baseline (hybrid): NDCG@5 0.707, MRR 0.815, Recall@5 0.783 (after adding one missing label to q06). With real notes in the corpus, hybrid now beats vector-only (0.702 vs 0.636 NDCG before that label fix), so the earlier "vector matches hybrid" concern is resolved for now. Remaining weak spots: questions with no shared vocabulary with the answer (q01, q14, q15). Next experiments if they matter: heading text weighted higher in FTS, and a larger chunk overlap. Questions were still written by Claude; replace them with real ones as they come up.

## Update (2026-10-21, embedding models and query prefix)
Golden set at 31 questions (8 real budget-app ones). Heading weight in FTS lowered scores at every weight (L-0019). Models tested in scratch indexes (`run_eval.py --model` now accepts any dimension there). The prefix is "Represent this sentence for searching relevant passages: ", on queries only.

| Model | Dims | NDCG@5 | MRR | Recall@5 |
|---|---|---|---|---|
| bge-small-en-v1.5 (current) | 384 | 0.558 | 0.641 | 0.661 |
| bge-small + prefix | 384 | 0.552 | 0.633 | 0.661 |
| snowflake-arctic-embed-s | 384 | 0.399 | 0.440 | 0.484 |
| arctic-embed-s + prefix | 384 | 0.580 | 0.669 | 0.661 |
| granite-embedding-small-english-r2 | 384 | 0.563 | 0.637 | 0.629 |
| gte-base | 768 | 0.579 | 0.678 | 0.677 |
| bge-base-en-v1.5 | 768 | 0.580 | 0.683 | 0.661 |
| bge-base + prefix | 768 | 0.588 | 0.688 | 0.661 |

Decision: stay on bge-small without a prefix. The best gain (bge-base + prefix, +0.030 NDCG) is about one question and equals the allowed noise, while it needs a 768-dim schema, a full re-index and a 3x larger model. Re-test bge-base + prefix and arctic-s + prefix when the golden set has grown; arctic-s is only usable with the prefix.

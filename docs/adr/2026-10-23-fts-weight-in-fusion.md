---
status: accepted
date: 2026-10-23
entities: [vault-index-server, adr-2026-10-20-search-tuning-round-1]
---

# ADR: Keyword ranks count at 0.1 in reciprocal rank fusion

## Context
Hybrid search fused FTS5 and vector ranks with equal weight (RRF, k = 60). On the public sample vault, vector-only beat hybrid (NDCG@5 0.773 vs 0.716): the FTS query ORs every content word, so paraphrased questions pull in noisy keyword matches. On the private vault the opposite held (hybrid 0.543, vector-only 0.522), because lesson ids, tool names and jargon need keywords. Heading weights in bm25 were already ruled out (L-0019).

## Decision
Weight keyword ranks at 0.1 and vector ranks at 1.0 in the fusion (`FTS_WEIGHT` in `mcp/server.py`); keep k = 60. Keywords now break ties and lift exact-term matches instead of casting an equal vote.

## Options considered
Sweep of fts weight (1.0 to 0.0) by k (10, 30, 60, 100) on both golden sets, from cached candidate lists (`hybrid_search` pools). The control row reproduced `run_eval.py` exactly. Keep rule fixed before the sweep: more than +0.03 NDCG@5 on one set and no drop on the other.

| fts weight, k | Private NDCG@5 (31 q) | Sample NDCG@5 (32 q) | Mean |
|---|---|---|---|
| 1.0, 60 (old) | 0.543 | 0.716 | 0.630 |
| 0.5, 60 | 0.549 | 0.755 | 0.652 |
| 0.3, 60 | 0.542 | 0.779 | 0.661 |
| 0.2, 60 | 0.552 | 0.774 | 0.663 |
| **0.1, 60** | **0.580** | **0.782** | **0.681** |
| 0.0, 60 (vector only) | 0.522 | 0.773 | 0.647 |
| 0.3, 10 | 0.559 | 0.799 | 0.679 |
| 0.8, 10 | 0.568 | 0.760 | 0.664 |

- 0.1 at k = 60 is the only config above +0.03 on both sets, and the mean rises steadily from 1.0 toward 0.1, then falls at 0.0.
- Lower k (10) helps the sample set more but is uneven on the private set; changing one knob is simpler.

## Consequences
- New baselines: private NDCG@5 0.579, MRR 0.669, Recall@5 0.645; sample in `eval/baseline.json` of the public repo.
- The private gain is churn-heavy (7 questions up, 6 down) and close to noise; the sample gain is clearer (11 up, 4 down). Re-check when the golden sets grow.
- `fts` and `vec` modes in `run_eval.py --modes all` still use full weight, so they keep measuring each side alone.
- Running MCP servers use the old fusion until restarted.

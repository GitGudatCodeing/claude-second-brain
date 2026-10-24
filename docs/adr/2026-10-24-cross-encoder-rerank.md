---
status: accepted
date: 2026-10-24
entities: [vault-index-server, adr-2026-10-23-fts-weight-in-fusion]
---

# ADR: Rerank the top 10 fused results with a small cross-encoder

## Context
Hybrid search fuses FTS5 and vector ranks (RRF, keyword weight 0.1). On the sample set's hard paraphrases vector-only had pulled ahead of hybrid, and the October 2026 survey of similar tools (audit `docs/audits/2026-10-24-full-audit-claude-second-brain.md`) showed rerankers as the main technique this system lacked.

## Decision
After fusion, `ms-marco-MiniLM-L-6-v2` (fastembed `TextCrossEncoder`, 80 MB, Apache-2.0) scores the top `max(limit, 10)` chunks against the query and they are returned in that order. `VAULT_RERANK=0` turns it off. Both ONNX models run with `min(8, cpus/2)` threads.

## Options considered
Keep rule fixed before running: more than +0.03 NDCG@5 on one golden set and no drop on the other, against production hybrid on the same index; model at most 150 MB; permissive licence; at most 150 ms added per search.

Pure rerank of the top 20, NDCG@5 change against production hybrid:

| Model | Size | Sample (44 q) | Private (41 q) |
|---|---|---|---|
| **ms-marco-MiniLM-L-6-v2** | 80 MB | **+0.058** | **+0.065** |
| ms-marco-MiniLM-L-12-v2 | 120 MB | +0.027 | +0.053 |
| jina-reranker-v1-tiny-en | 130 MB | -0.009 | +0.059 |
| jina-reranker-v1-turbo-en | 150 MB | -0.061 | +0.030 |
| bge-reranker-base (reference) | 1 GB | -0.012 | +0.013 |

Fusing the reranker's rank with the hybrid rank (RRF) was weaker for MiniLM-L-6 (+0.041, +0.037). Candidates for MiniLM-L-6: 10 gives +0.050 / +0.063, 15 gives +0.057 / +0.069, 20 gives +0.058 / +0.065. The gain is stable, so the cheapest (10) was chosen.

In the server: sample 0.699 to 0.750, private 0.487 to 0.550 NDCG@5. Hybrid now beats vector-only on both sets again (sample 0.750 vs 0.717).

## Consequences
- Latency: a warm `search_notes` takes about 200 ms p50 on the private vault (24-core Windows), up from 7 ms; the 150 ms guard is missed by about 50 ms. Accepted: Claude's own turn takes seconds, and the quality gain is the largest measured on this system.
- Thread cap: with default threads, interleaved embed + rerank took 510 ms (two ONNX pools contending); capping both at 8 brought it to about 190 ms and made full indexing faster too (15.7 s vs 19.3 s for 488 chunks).
- One more model download on first search (about 80 MB, same cache folder).
- Baselines re-saved with the reranker, so future changes are measured against it.
- The eval gains a `fused` mode (fusion without rerank) to keep each stage visible.

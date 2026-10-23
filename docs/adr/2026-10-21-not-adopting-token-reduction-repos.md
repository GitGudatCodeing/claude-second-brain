---
status: accepted
date: 2026-10-21
entities: [secondbrain, vault-index, context-guard]
---

# ADR: Not adopting third-party token-reduction repos

## Context
Reviewed rtk, snip, context-mode, caveman, claude-token-efficient, token-savior, code-review-graph and reducethemtokens against their READMEs (2026-10-21).
- Our token cost is long sessions, Gmail `search_threads` output and browser screenshots. It is not shell output or code reading.
- The vault is markdown and `vault-index` already serves it. Most repos target code (Tree-sitter) or Bash output only.
- All savings figures are self-reported. Several add input tokens (caveman about 1,160, claude-token-efficient per message) or heavy hooks (context-mode: 11 tools, 6 hooks).
- Licenses: rtk engine is BUSL-1.1, context-mode is ELv2 (both source-available).

## Decision
Adopt none. Keep our own measures: context guard (300k/450k), lesson L-0017 (page text over screenshots), small Gmail pages with metadata-only views, `.ignore` for `mcp/.venv/`.

## Options considered
- rtk / snip: filter Bash output only; little noisy shell output here. snip has unclear Windows support.
- context-mode: best fit (sandboxes large MCP output) but heavy, source-available, claims unverified.
- caveman / claude-token-efficient: our CLAUDE.md already asks for concise replies; their rules cost input tokens.
- token-savior / code-review-graph / reducethemtokens: code-only indexing; `vault-index` covers notes.

## Consequences
- No new dependencies, hooks or licenses to maintain.
- Revisit context-mode if MCP tool output stays the top token cost; rtk if shell output grows.
- Any trial: measure with and without on a throwaway session, keep only if it wins.

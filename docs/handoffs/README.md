# Handoffs

Notes that carry work from one session to the next (`/handoff`). One file per handoff: `YYYY-MM-DD-<topic>.md`, `status: open` until a new session picks it up.

- Triggered by hand, or by `scripts/context_guard.py` when a session passes the limits in `.claude/handoff.json`.
- `auto/`: pre-compaction snapshots from `scripts/precompact_snapshot.py`. A fallback only; not indexed.

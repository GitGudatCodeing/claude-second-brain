---
status: accepted
date: 2026-09-28
entities: [recipe-box]
---

# ADR: Recipe box stores data in SQLite

## Context
At most a few hundred recipes and a dozen users, on one small VPS. Alex wants nothing to patch or tune.

## Decision
One SQLite file in WAL mode. Full-text search with FTS5. Backups with the `.backup` command, copied off the server nightly.

## Options considered
- PostgreSQL: familiar from work and better for many writers, but another service to run, upgrade and back up.
- A hosted database: no maintenance, but a monthly bill and a network hop for every page.

## Consequences
- Deploys are one file and one process.
- If the app ever needs several servers, migrate to Postgres. Not expected.

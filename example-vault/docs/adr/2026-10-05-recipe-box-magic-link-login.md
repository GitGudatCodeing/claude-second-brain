---
status: accepted
date: 2026-10-05
entities: [recipe-box]
---

# ADR: Recipe box login with emailed magic links

## Context
Most users are relatives on phones; two are over 75 and forget passwords. Jordan's idea of no accounts at all fails because edits need a name attached.

## Decision
Log in by entering an email address and clicking a one-time link. Links expire after 30 minutes; sessions last 90 days.

## Options considered
- Passwords: well understood, but resets would land on Alex every month.
- No accounts, one shared family link: simplest, but anyone with the link can delete recipes.
- Sign in with Google: not everyone has an account, and it adds a dependency.

## Consequences
- Needs a transactional email provider; the free tier covers the volume.
- Email delivery delays become login delays. Test with the relatives' real providers first.

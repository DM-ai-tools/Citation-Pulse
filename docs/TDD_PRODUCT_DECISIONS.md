# TDD §17 — Product decisions (locked for implementation)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Slack app vs incoming webhook v1? | **Incoming webhooks** for v1 | Lowest integration cost; Slack app + OAuth in a later iteration. |
| Competitor storage: flat per brand vs shared taxonomy? | **Per-brand `competitors uuid[]`** referencing other `brands` rows in the same tenant | Matches TDD DDL; reusable taxonomy can be a later migration without breaking v1. |
| Sentiment: per-snippet Haiku vs nightly batch? | **Per-snippet with SHA256 LRU cache** (`services/sentiment.py`) | Bounded cost for hot snippets; switch to nightly batch if spend exceeds budget. |
| Public API in Phase 2 vs Phase 3? | **Phase 3** — partner REST + `WebhookSubscription` + HMAC signatures ship with agency mode | Phase 2 focuses on Clerk + Stripe + dashboard; `/api/v1` partner routes exist as scaffolding. |
| AIO SLA? | **Best-effort only** — no percentage SLA in contracts | Scrape-only surface; synthetic canary + disclaimers in customer-facing docs. |

## White-label / agency

- **Theming:** store agency palette in `tenants.settings` JSON (e.g. `theme.primary`) and read in Next.js layout when `tenant` context is available (Phase 3 UI pass).

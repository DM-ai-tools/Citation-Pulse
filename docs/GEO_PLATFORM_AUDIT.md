# CitationPulse GEO Platform — Architecture Audit

**Audit date:** 2026-05-06  
**Update (2026-05-07):** The legacy `client/` (Vite) and `server/` (Express) trees referenced below have been **deleted** from the repo. The GEO product implementation now lives under **`apps/api`**, **`apps/web`**, and **`infra/`** (TDD section 18 layout). This document is preserved as a **historical gap analysis** only.

**Source of truth requested:** Technical Design Document + UI mockups *(not present in repository; this audit uses the specification from the stakeholder brief as the target architecture).*  
**Codebase audited:** `client/`, `server/`, root workspace *(as of audit date — both folders have since been removed)*.

---

## Executive summary

| Area | Status vs target spec |
|------|------------------------|
| Product intent | **Mismatch.** Repository implements a **crypto exchange API documentation** SPA + Express API, not a **GEO / AI citation monitoring** product. |
| Mandatory stack | **Mismatch.** Target: Next.js 15, FastAPI, Celery, Playwright, Clerk, Stripe, R2, Sentry, OTel. **Actual:** Vite + React, Express, optional PGlite/Postgres, JWT/HMAC auth. |
| Domain modules (engines, SoV, gaps, alerts, operator console) | **Absent** in current `client`/`server`. |
| Attached TDD / mockups | **Not found** in-repo (no PDF/MD/Figma links checked in). Gap analysis cannot be pixel-compared to mockups without those assets. |

**Conclusion (historical):** The **`client/`** and **`server/`** trees did **not** implement the GEO platform. Remediation was to add a separate GEO stack; that stack is now **`apps/api`**, **`apps/web`**, and **`infra/`** (not `platform/`). The gap list below still describes what was missing from the legacy demo.

---

## 1. What matches (minimal)

| Item | Notes |
|------|--------|
| Brand name reuse | Project is named CitationPulse in README; domain meaning differs (crypto API docs vs GEO). |
| PostgreSQL concept | Server uses SQL migrations; **no pgvector**, **no multi-tenant GEO schema**. |
| REST API pattern | Express exposes `/v1/*`; **not** the GEO resource model. |
| Rate limiting | Simple IP bucket in Express — **not** per-tenant/engine adapter limits from spec. |

---

## 2. What is missing (by module)

### 1. Authentication
| Requirement | Gap | Priority |
|-------------|-----|----------|
| Clerk | Not integrated; custom JWT + API keys only. | P0 |
| JWT validation (Clerk) in backend | N/A; would need JWKS validation in FastAPI. | P0 |
| Protected routes (Next.js) | N/A; Vite SPA has no Clerk middleware. | P0 |
| Tenant/workspace creation | No `tenants` / workspace model in Express schema. | P0 |
| MFA | Not present. | P1 |

### 2. Onboarding
| Requirement | Gap | Priority |
|-------------|-----|----------|
| Brand / competitor / prompt / alert wizard | Not present. | P0 |
| First run trigger | Not present. | P0 |

### 3. Dashboard
| Requirement | Gap | Priority |
|-------------|-----|----------|
| KPI cards, trends, engine charts | Docs landing only; no Recharts, no TanStack Query. | P0 |
| Run status, PDF export, realtime | Not present. | P1–P0 |

### 4. Engine adapters
| Engine | Gap | Priority |
|--------|-----|----------|
| ChatGPT / Claude / Gemini / Perplexity / Google AIO | No adapter interface, no parsing, retries, cost tracking, raw storage. | P0 |

### 5. Playwright
| Requirement | Gap | Priority |
|-------------|-----|----------|
| Google AIO scraping, screenshots, HTML, proxies | Not present. | P0 |

### 6. Redis + Celery
| Requirement | Gap | Priority |
|-------------|-----|----------|
| Queues, schedules, retries, concurrency, fanout, browser pool | Not present (Express has in-proc WS only). | P0 |

### 7. Database
| Table / feature | Gap | Priority |
|-----------------|-----|----------|
| tenants, brands, prompts, engine_runs, citations, alerts | Express schema has users, orders, balances, api_credentials. | P0 |
| pgvector, RLS readiness | Absent. | P0 |

### 8. Citation normalization
| Requirement | Gap | Priority |
|-------------|-----|----------|
| URL canonicalization, ownership, semantic dedupe, sentiment | Not present. | P0 |

### 9. Share of Voice
| Requirement | Gap | Priority |
|-------------|-----|----------|
| SoV engine, aggregation, competitor trends | Not present. | P0 |

### 10. Gap detection
| Requirement | Gap | Priority |
|-------------|-----|----------|
| Missing brand, competitor-only prompts, scoring | Not present. | P0 |

### 11. Alerts
| Requirement | Gap | Priority |
|-------------|-----|----------|
| Slack, email, dedupe, nightly jobs | Not present. | P0 |

### 12. Operator console
| Requirement | Gap | Priority |
|-------------|-----|----------|
| DFY workflows, gap reports, client bulk ops | Not present. | P1 |

### 13. Observability
| Requirement | Gap | Priority |
|-------------|-----|----------|
| Sentry, OpenTelemetry, structured logs, metrics | Not integrated in Express/Vite app. | P1 |

### 14. Security
| Requirement | Gap | Priority |
|-------------|-----|----------|
| Tenant isolation, Clerk sessions, CORS for Next+API | Partial CORS on Express only; no tenant boundary. | P0 |
| Secrets in repo | `.env` gitignored; **verify** no secrets committed. | P0 |

### 15. Deployment
| Requirement | Gap | Priority |
|-------------|-----|----------|
| Railway, Dockerfiles, monorepo for GEO stack | Only npm workspaces for client/server. | P1 |

### UI/UX vs mockups
| Requirement | Gap | Priority |
|-------------|-----|----------|
| Layout, nav, onboarding, operator console, palette | Current UI is **API docs** layout; mockups not in repo for diff. | P0 (after assets) |

---

## 3. Incorrect / partial (if interpreted as GEO product)

- **Product positioning:** README and UX describe crypto trading API — incorrect for GEO monitoring.
- **“CitationPulse” naming collision:** Same name, different product; risks confusion until README clarifies dual packages or deprecation path.

---

## 4. Recommended remediation strategy (preserves existing code)

1. **Keep** `client/` and `server/` as **legacy / API docs demo** (or rename in README to “Legacy”).
2. **Add** a GEO tree (**`apps/api`**, **`apps/web`**, **`infra/`**) with **Next.js 15 + FastAPI + Celery + Docker (Postgres pgvector + Redis)** as the implementation baseline.
3. **Import** official TDD + mockups into `docs/` when available; run a second UI audit pass for pixel parity.
4. **Migrate** features incrementally: auth → schema → adapters → workers → dashboards.

---

## 5. Production readiness (GEO spec)

| Dimension | Score (0–5) | Comment |
|-----------|-------------|---------|
| Auth & tenancy | 0 | Clerk/tenant model missing in current tree. |
| Core domain | 0 | No citations/engines/SoV. |
| Workers & scale | 0 | No Celery/Redis. |
| Data model | 0 | Wrong schema for GEO. |
| Observability | 0–1 | Not wired. |
| Security | 1 | Basic rate limit + JWT in legacy API only. |

**Overall GEO readiness (legacy-only):** **~0%** on `client`/`server` as audited; use **`apps/*`** and **`infra/`** for current GEO implementation status.

---

## 6. Blockers

- **Missing TDD/mockups in repo** — cannot close UI/UX validation loop.
- **Full implementation** is large (months); scaffold + phased delivery required.
- **Third-party accounts:** Clerk, Stripe, R2, Railway, Sentry — need org provisioning and env secrets.

---

## Post-audit implementation

GEO scaffolding and subsequent implementation use **`apps/api`**, **`apps/web`**, and **`infra/`**. Legacy **`client/`** + **`server/`** are unchanged. See root [`README.md`](../README.md) and [`TDD_PRODUCT_DECISIONS.md`](./TDD_PRODUCT_DECISIONS.md).

*End of audit.*

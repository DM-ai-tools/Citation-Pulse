# Project cleanup report

**Date:** 2026-05-19  
**Scope:** Conservative cleanup of verified unused code in the active monorepo (`apps/web`, `apps/api`). Legacy deploy trees were analyzed but **not removed**.

---

## Summary

| Action | Count |
|--------|------:|
| Files deleted | 14 |
| Build artifacts removed | 2 directories (`*.egg-info`) |
| npm packages removed | 0 (see notes) |
| Dead exports trimmed | 3 functions in 2 files |
| Build fix (stability) | 1 (`app/page.tsx` async cookies) |

**Verification:** `npm run lint`, `npm run test`, and `npm run build` for `citationpulse-web` all succeed.

---

## Deleted files

| Path | Reason |
|------|--------|
| `apps/web/src/lib/useDashboardBrandId.ts` | `@deprecated` wrapper; zero imports; replaced by `useDashboardWorkspace` |
| `apps/web/src/components/dashboard/GapsAnalysisSection.tsx` | `@deprecated` re-export of `GapsPanel`; zero imports |
| `apps/web/src/components/report/CompetitorCitationRankings.tsx` | Component never imported |
| `apps/web/src/components/report/Breakdown.tsx` | Component never imported |
| `apps/web/src/components/report/CitationsList.tsx` | Component never imported |
| `apps/web/src/services/opportunities.ts` | Service never imported |
| `apps/web/src/lib/gapOpportunityDetail.ts` | Module never imported |
| `apps/web/src/components/shared/StatusPill.tsx` | Component never imported |
| `apps/web/src/components/shared/EngineBadge.tsx` | Component never imported |
| `apps/web/src/components/primitives/Chip.tsx` | Exported but never used |
| `apps/web/src/components/primitives/Pill.tsx` | Exported but never used |
| `apps/web/src/components/primitives/Tabs.tsx` | Exported but never used |
| `apps/web/src/components/primitives/ProgressBar.tsx` | Exported but never used |
| `apps/api/src/citationpulse_api.egg-info/` | Pip build artifact (regenerated on install) |
| `backend/src/citationpulse_api.egg-info/` | Same (legacy tree) |

---

## Removed dependencies

| Package | Status |
|---------|--------|
| `@tanstack/react-table` | **Already absent** from `apps/web/package.json` at cleanup time; no lockfile change required |

No other npm or Python packages were removed (all remaining deps are referenced or optional at runtime, e.g. Clerk when env key is set).

---

## Code trimmed (not deleted)

| File | Change |
|------|--------|
| `apps/web/src/lib/passwordStrength.ts` | Removed unused `passwordStrengthScore` and `passwordStrengthLabel` |
| `apps/web/src/lib/format.ts` | Removed unused `pct()` (only used by deleted `Breakdown.tsx`) |
| `apps/web/src/components/primitives/index.ts` | Removed exports for deleted primitives |

---

## Configuration / hygiene

| Change | Reason |
|--------|--------|
| `.gitignore` — added `*.egg-info/` | Prevent committing pip build metadata |

---

## Build stability fix (related)

| File | Fix |
|------|-----|
| `apps/web/src/app/page.tsx` | `cookies()` is async in Next.js 15; page made `async` so production build passes |

---

## Uncertain items — **not removed** (manual decision required)

### Legacy duplicate trees (~150+ files each)

| Path | Notes |
|------|--------|
| `frontend/` | Railway deploy copy of `apps/web` (per `.gitignore`); still referenced by `frontend/railway.json` |
| `backend/` | Railway deploy copy of `apps/api`; **stale** vs `apps/api` (missing auth/admin/gap modules); `infra/railway/backend.railway.json` points here |

**Recommendation:** Migrate Railway services to `apps/web` and `apps/api` + `infra/railway/{web,api,worker}.railway.json`, then delete `frontend/` and `backend/`.

### Unlinked but routable admin pages

| Path | Notes |
|------|--------|
| `apps/web/src/app/admin/(panel)/analytics/page.tsx` | Removed from admin nav; route still works |
| `apps/web/src/app/admin/(panel)/gaps/page.tsx` | Same |
| `apps/web/src/app/admin/(panel)/settings/page.tsx` | Same |

Kept intentionally — valid routes, may be bookmarked or linked externally.

### OpenAPI / shared types

| Path | Notes |
|------|--------|
| `packages/shared-types/` | `openapi.json` + generated `api.d.ts` not imported in app code; **kept** for `npm run typegen` contract workflow |

### Optional auth dependency

| Package | Notes |
|---------|--------|
| `@clerk/nextjs` | Used in `providers.tsx` when `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set; native auth is default — **kept** for dual-mode support |

### Script aliases (harmless)

Root `package.json`: `dev:geo:web`, `build:geo:web`, `lint:geo:web`, `dev:stack`, `start:all` — redundant aliases, documented in README/SETUP; not removed.

---

## Remaining lint warnings (non-blocking)

| Location | Warning |
|----------|---------|
| `apps/web/src/app/login/page.tsx` | `setRemember` assigned but unused |
| `apps/web/src/lib/useDashboardWorkspace.ts` | `react-hooks/exhaustive-deps` on `tenantBrands` in `useMemo` |

---

## Test results

| Command | Result |
|---------|--------|
| `npm run lint -w citationpulse-web` | Pass (warnings only) |
| `npm run test -w citationpulse-web` | Pass (3 tests) |
| `npm run build -w citationpulse-web` | Pass |
| `apps/api` pytest | Run if `.venv` present locally |

---

## Optimizations performed

- Smaller primitives barrel (`index.ts`) — fewer unused exports for bundlers/IDE
- ~25 KB+ source removed (unused components/services)
- `.gitignore` hardened against `egg-info` churn
- Production build unblocked for root `/` redirect page

---

## Next cleanup phase (optional)

1. Delete `frontend/` + `backend/` after Railway migration
2. Remove or wire admin analytics/gaps/settings pages
3. Drop `@clerk/nextjs` if Clerk is permanently retired
4. Adopt or drop `packages/shared-types` generated types in `apps/web`
5. Run `knip` / `depcheck` in CI for ongoing unused-code detection

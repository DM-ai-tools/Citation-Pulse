# Authentication enforcement audit report

**Date:** 2026-05-20  
**Scope:** Full-stack auth lockdown for CitationPulse (`apps/web` + `apps/api`)

---

## Summary

Authentication is now **required** for search (landing scan), dashboard, reports, live scans, and all tenant data APIs. Unauthenticated users are redirected to **`/login`**. The default route **`/`** always sends unauthenticated users to login.

**Exception (by design):** Token-based public share links (`/r/[token]` + `GET /api/v1/scans/public/{token}`) remain available without an account so shared reports can still be viewed.

---

## Protections added

### Frontend (Next.js)

| Layer | Implementation |
|-------|----------------|
| **Edge middleware** | JWT verification via `jose` + `AUTH_JWT_SECRET` (same as API); rejects forged/empty cookies in production |
| **Route policy** | Public only: `/login`, `/signup`, `/privacy`, `/terms`, `/admin/login`, `/r/*` |
| **Default `/`** | Unauthenticated → `/login`; authenticated → `/landing` |
| **Client guards** | `RequireAuth` on dashboard, scan, report, landing layouts |
| **Admin** | `RequireAdmin` on admin panel (role from session, not cookie alone in production) |
| **API client** | All `apiFetch` calls require Bearer token; `401` clears session and redirects to login |
| **Redirect after login** | Honors `?next=` query param |

### Backend (FastAPI)

| Area | Implementation |
|------|----------------|
| **Scans** | All routes except `GET /public/{token}` require `get_auth_context` |
| **Scan tenancy** | `_assert_scan_tenant` — users only access scans in their tenant |
| **Create scan** | Uses authenticated user's tenant (no anonymous tenant for logged-in scans) |
| **Competitors** | `POST /competitors/analyze` requires auth |
| **Brands / billing / admin** | Already behind `get_auth_context` / `require_admin` |
| **Tenant resolution** | Removed unsafe “first tenant in DB” fallback in production |

---

## Files modified

### Web
- `apps/web/src/middleware.ts` — strict route policy + JWT verification
- `apps/web/src/lib/sessionToken.ts` — **new** JWT verify helper
- `apps/web/src/lib/authRedirect.ts` — `next` param support
- `apps/web/src/services/apiClient.ts` — auth required, 401 handling, `publicApiFetch`
- `apps/web/src/services/report.ts` — public share uses `publicApiFetch`
- `apps/web/src/components/auth/RequireAuth.tsx` — **new**
- `apps/web/src/components/auth/RequireAdmin.tsx` — **new**
- `apps/web/src/app/(auth)/layout.tsx`
- `apps/web/src/app/(marketing)/landing/layout.tsx` — **new**
- `apps/web/src/app/scan/layout.tsx` — **new**
- `apps/web/src/app/report/layout.tsx` — **new**
- `apps/web/src/app/admin/(panel)/layout.tsx`
- `apps/web/package.json` — added `jose`
- `apps/web/.env.example` — `AUTH_JWT_SECRET`

### API
- `apps/api/src/citationpulse/api/v1/scans.py` — auth router + tenant checks
- `apps/api/src/citationpulse/api/v1/competitors.py` — auth required
- `apps/api/src/citationpulse/api/deps.py` — production tenant resolution tightened

---

## Security improvements

1. **No anonymous scan API** — `POST /api/v1/scans` requires valid session.
2. **No public report by scan UUID** — report/SoV/stream endpoints require auth + tenant match.
3. **Middleware JWT validation** — `cp_token` cookie alone is insufficient when `AUTH_JWT_SECRET` is set on web.
4. **401 handling** — expired/revoked sessions redirect to login.
5. **Admin role** — derived from verified JWT claims in middleware (not `cp_role` cookie when secret configured).

---

## Remaining warnings / notes

| Item | Severity | Notes |
|------|----------|-------|
| `jose` Edge runtime warnings | Low | Build warns about CompressionStream; HS256 verify still works |
| `cp_role` cookie | Low | Still set for dev fallback when web has no `AUTH_JWT_SECRET` |
| Token in localStorage | Medium | XSS could steal token; HttpOnly cookie migration is a future hardening |
| Public share links | Info | `/r/{token}` intentionally public |
| Legacy scans (anonymous tenant) | Info | Pre-auth scans not visible to new users until re-run under their account |
| `useDashboardWorkspace` hook deps | Low | ESLint warning only |

---

## Environment (required for production)

Set on **both API and Web** Railway services:

```env
AUTH_JWT_SECRET=<same 32+ char secret on both services>
ENVIRONMENT=production
INTERNAL_PHASE1=false
```

Web service also needs `AUTH_JWT_SECRET` (server-only, not `NEXT_PUBLIC_*`) for middleware JWT verification.

Local dev: copy the same `AUTH_JWT_SECRET` from root `.env` into `apps/web/.env.local`.

---

## Verification performed

| Check | Result |
|-------|--------|
| `npm run build -w citationpulse-web` | Pass |
| Middleware bundle | 40.3 kB (includes jose) |

### Manual test checklist

1. Open `http://localhost:3000/` → redirects to `/login`
2. Visit `/dashboard`, `/landing`, `/report/any-id` logged out → `/login?next=...`
3. Login → lands on `next` or `/landing`
4. Run scan on landing → succeeds with Bearer token
5. Logout → `/login`; revisit dashboard → blocked
6. `GET /api/v1/brands` without token → `401`
7. `GET /api/v1/scans/public/{valid-share-token}` without token → `200` (share only)

---

## Deployment readiness

**Ready for Railway** after setting `AUTH_JWT_SECRET` on **Web + API** and redeploying both services.

See also: `RAILWAY_DEPLOY.md`, `infra/railway/README.md`.

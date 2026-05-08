# CitationPulse Web (`apps/web`)

Next.js 15 + Tailwind + TanStack Query + TanStack Table + Recharts + optional Clerk + Sonner toasts.

## Setup

```bash
cd apps/web
cp .env.example .env.local   # if present; else set NEXT_PUBLIC_API_URL
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Scan funnel (public)

- `/` — landing + free scan form → `POST /api/v1/scans`
- `/scan/[scanId]` — live matrix + SSE (`/api/v1/scans/{id}/stream`)
- `/report/[scanId]` — full report (heatmap, matrix, gaps, share)
- `/r/[shareToken]` — public shared report

## OpenAPI types

Export schema from the API (monorepo root):

```bash
cd apps/api
set PYTHONPATH=src   # PowerShell: $env:PYTHONPATH="src"
python scripts/export_openapi.py
cd ../../apps/web
npm run typegen
```

## Tests

```bash
npm run test        # Vitest (scan SSE reducer)
npm run test:e2e    # Playwright (needs dev server + npx playwright install)
```

## Clerk

When `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is a real key (≥32 chars, not `placeholder`), `ClerkProvider` wraps the app. Route protection can be added in `middleware.ts` (currently a no-op stub).

## React version (monorepo)

`apps/web` must resolve **React 18.3.1** with the rest of the workspace. If `npm ls react -w citationpulse-web` shows `19.x` under `apps/web/node_modules`, refresh the lockfile:

```bash
npm install react@18.3.1 react-dom@18.3.1 -w citationpulse-web --save-exact
```

(from monorepo root)

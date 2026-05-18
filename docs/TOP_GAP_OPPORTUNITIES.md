# Top Gap Opportunities — integration guide

This module detects **prompts where competitors are cited by AI engines but the
brand is missing or weakly represented**, grades them A/B/C, and surfaces them
in the dashboard. The dashboard reads precomputed rows from the
`opportunities` table — **no math runs at request time**.

```
prompts.demand_*        →  refresh_demand   (weekly Celery beat)
engine_runs / citations →  normalise        (per scan)
                       →  score_cells      (per scan)
                       →  detect_opportunities (nightly Celery beat)
                       →  opportunities table
                       →  GET /api/v1/brands/{id}/opportunities
                       →  <TopGapOpportunities /> in the dashboard
```

## What's in the box

| Layer        | Path                                                                 |
|--------------|----------------------------------------------------------------------|
| Migration    | `infra/sql/20260514_demand_resolution.sql`                           |
| Runtime DDL  | `backend/src/citationpulse/db/runtime_bootstrap.py`                  |
| ORM          | `backend/src/citationpulse/models/domain.py` (`Prompt`, `Opportunity`) |
| Cache        | `backend/src/citationpulse/services/cache.py`                        |
| Demand       | `backend/src/citationpulse/services/demand.py`                       |
| Scoring      | `backend/src/citationpulse/services/opportunities.py`                |
| Celery tasks | `backend/src/citationpulse/tasks/geo.py` (`refresh_demand`, `detect_opportunities`) |
| Schedules    | `backend/src/citationpulse/celery_app.py`                            |
| Schemas      | `backend/src/citationpulse/schemas/brands.py`                        |
| API          | `backend/src/citationpulse/api/v1/endpoints.py`                      |
| Frontend     | `frontend/src/components/report/TopGapOpportunities.tsx`             |
| Service hook | `frontend/src/services/brands.ts`                                    |
| Types        | `frontend/src/types/report.ts`                                       |
| Tests        | `backend/tests/test_top_gap_opportunities.py`                        |

## Required environment variables

```bash
# Postgres (already required by the rest of the stack)
DATABASE_URL=postgresql+psycopg://...

# Optional but recommended — caches DataForSEO lookups for 7 days
REDIS_URL=redis://default:password@host:6379/0

# Optional — enables DataForSEO literal/variant demand steps
DATAFORSEO_LOGIN=...
DATAFORSEO_PASSWORD=...

# Optional tuning (defaults shown)
DEMAND_MIN_LITERAL_VOLUME=50
DEMAND_MIN_VARIANT_VOLUME=50
DEMAND_HIGH_VOLUME=5000
DEMAND_MEDIUM_VOLUME=500
```

When `REDIS_URL` is unset the cache module falls back to an in-process LRU so
the pipeline still runs. When DataForSEO credentials are unset the resolver
skips steps 1 and 2 and uses the internal composite or the default fallback.

## Apply the migration

Either:

```powershell
# 1) Use the runtime bootstrap (idempotent) — happens automatically when the
#    API or a Celery worker starts. No action needed in production.

# 2) Or run the .sql file manually:
$env:DATABASE_URL = "postgresql+psycopg://..."
psql $env:DATABASE_URL -f infra/sql/20260514_demand_resolution.sql
```

## API

### `GET /api/v1/brands/{brand_id}/opportunities`

Read precomputed opportunity rows.

Query params:

| Name        | Type    | Default | Description                                                                          |
|-------------|---------|---------|--------------------------------------------------------------------------------------|
| `status`    | string  | `open`  | `open` \| `snoozed` \| `queued` \| `resolved`                                        |
| `grade`     | string  | —       | `A` \| `B` \| `C` (exact match)                                                      |
| `gap_type`  | string  | —       | `absent_all` \| `competitor_dominant` \| `engine_specific_gap` \| `weak_engine` \| `refresh_content` \| `extend_presence` |
| `limit`     | int     | 100     | Page size (1–500)                                                                    |
| `offset`    | int     | 0       | Pagination offset                                                                    |
| `paginated` | bool    | `false` | When `true`, response is `{items, total, limit, offset, has_more}`                   |

Sort order:

1. Grade A → B → C
2. `opportunity_score DESC`
3. `detected_at DESC` (tiebreaker)

Example (flat list):

```json
[
  {
    "id": "8c4e…",
    "brand_id": "12ab…",
    "prompt_id": "78ef…",
    "title": "best CRM for SMB",
    "gap_type": "absent_all",
    "scope": null,
    "grade": "A",
    "heat": "HOT",
    "opportunity_score": 0.82,
    "description": "Brand absent across all 4 engines · 8.1k/mo searches",
    "est_volume": 8100,
    "status": "open",
    "detected_at": "2026-05-13T05:00:00+00:00",
    "demand_score": 0.83,
    "demand_bucket": "high",
    "demand_pill": "HIGH",
    "demand_source": "literal",
    "demand_variant": "best crm for smb",
    "demand_raw_volume": 8100,
    "demand_refreshed_at": "2026-05-12T04:00:00+00:00"
  }
]
```

Example (paginated envelope):

```json
{
  "items": [/* ... */],
  "total": 47,
  "limit": 25,
  "offset": 25,
  "has_more": false
}
```

## Background jobs

| Task                                  | Schedule                | Purpose                                                  |
|---------------------------------------|-------------------------|----------------------------------------------------------|
| `citationpulse.refresh_demand`        | Sundays 04:00 UTC       | Recompute `prompts.demand_*` for prompts >7d old         |
| `citationpulse.detect_opportunities`  | Daily 05:00 UTC         | Re-classify gaps, score, upsert/resolve opportunity rows |

Both tasks are idempotent. Resolved opportunities **are kept in the table**
with `status='resolved'` for audit purposes.

Trigger manually (e.g. for one brand):

```python
from citationpulse.tasks.geo import detect_opportunities_task, refresh_demand_task
refresh_demand_task.delay(brand_id="…")          # refresh demand first
detect_opportunities_task.delay(brand_id="…")    # then score gaps
```

## Demand resolution — the 4-step fallback

1. **Literal** — DataForSEO Google Ads volume for the prompt text.
   Valid iff volume ≥ `DEMAND_MIN_LITERAL_VOLUME`.
2. **Variant** — Decompose into 2–5 short keyword variants and take the highest volume ≥ `DEMAND_MIN_VARIANT_VOLUME`.
3. **Internal** — Composite of answer richness × engine consensus × cross-tenant crowd similarity (`0.4r + 0.3c + 0.3w`).
4. **Default** — Hard floor: `demand_score = 0.30`, `demand_bucket = "unknown"`.

Volumes are cached in Redis (or in-process when no Redis) for 7 days, keyed
by `(variant, locale)`, so the weekly refresh job is cheap even at scale.

## Scoring

```
score = 0.40 * demand
      + 0.30 * gap            (missing + 0.5 * competitor_only) / n_engines
      + 0.20 * comp_cscore    min(competitor_cites / n_engines, 1)
      + 0.10 * persist        min(consecutive_gap_runs / 7, 1)
```

Special rule: when `gap_type == "absent_all"` AND `demand_bucket == "high"`,
the score is floored at **0.71** so it always grades A.

```
A ≥ 0.70    B ≥ 0.40    C < 0.40
```

`HOT` / `WARM` / `COOL` heat pills are derived from the grade.

## Frontend

```tsx
import { TopGapOpportunities } from "@/components/report/TopGapOpportunities";
import { getBrandOpportunities } from "@/services/brands";

const q = useQuery({
  queryKey: ["brand-opportunities", brandId],
  queryFn: () => getBrandOpportunities(brandId, "open"),
});

return (
  <TopGapOpportunities
    opportunities={q.data ?? []}
    isLoading={q.isPending}
    isError={q.isError}
    onRetry={() => q.refetch()}
  />
);
```

The component renders:

- Grade badge (`A`/`B`/`C`)
- Row title (`prompt · engine_label`)
- Subtitle/description (templated, no LLM)
- **Demand pill** — `HIGH`/`MEDIUM`/`LOW`/`UNKNOWN` (raw volume hidden)
- Hover tooltip with raw volume, source, variant, normalised score, refreshed_at
- `HOT`/`WARM`/`COOL` heat pill
- Loading / empty / retry states

## Testing

```powershell
cd backend
python -m pytest tests/test_top_gap_opportunities.py -q
```

Covers:

- All 6 classifier rules + priority order
- `opportunity_score` honours `demand_bucket="high"` for `absent_all`
- Grade thresholds
- Volume → bucket / score helpers
- Prompt decomposition (`"cheapest way to hire a handyman in Sydney"` etc.)
- 4-step `resolve_demand` fallback (literal → variant → internal → default)
- Redis cache wrapper falls back to in-process when no `REDIS_URL`

## Operational notes

- **Pipeline ordering** is enforced by the Celery beat schedule:
  `normalise → score_cells → detect_opportunities`. Do **not** schedule
  `detect_opportunities` on its own without normalise+score running first.
- The `UNIQUE (brand_id, prompt_id, gap_type, scope)` constraint is what
  stops the nightly job from creating duplicate rows. Don't drop it.
- DataForSEO volumes update monthly. Schedule `refresh_demand` weekly so
  bucket transitions surface within ~7 days.
- Always prefer **upsert + resolve** over delete: operators need the audit
  trail of historical opportunities for retros and reporting.

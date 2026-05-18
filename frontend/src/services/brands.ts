import { apiFetch } from "./apiClient";
import type {
  OpportunityListResponse,
  OpportunityQuery,
  OpportunityRow,
} from "@/types/report";

/** Build the querystring for `/brands/{id}/opportunities`, omitting undefined keys. */
function buildOpportunityQuery(q: OpportunityQuery): string {
  const params = new URLSearchParams();
  if (q.status) params.set("status", q.status);
  if (q.grade) params.set("grade", q.grade);
  if (q.gap_type) params.set("gap_type", q.gap_type);
  if (typeof q.limit === "number") params.set("limit", String(q.limit));
  if (typeof q.offset === "number") params.set("offset", String(q.offset));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

function normaliseRow(o: OpportunityRow): OpportunityRow {
  return {
    ...o,
    detected_at: o.detected_at == null ? null : String(o.detected_at),
    demand_refreshed_at:
      o.demand_refreshed_at == null ? null : String(o.demand_refreshed_at),
  };
}

/**
 * Open (or other) gap opportunity rows for dashboard / brand views.
 *
 * Pass `status` directly or a full `OpportunityQuery` to apply filters
 * (grade / gap_type) and pagination. Returns a flat list.
 */
export async function getBrandOpportunities(
  brandId: string,
  statusOrQuery: OpportunityQuery["status"] | OpportunityQuery = "open",
): Promise<OpportunityRow[]> {
  const query: OpportunityQuery =
    typeof statusOrQuery === "string"
      ? { status: statusOrQuery }
      : { status: "open", ...statusOrQuery };
  const r = await apiFetch(
    `/api/v1/brands/${encodeURIComponent(brandId)}/opportunities${buildOpportunityQuery(query)}`,
  );
  if (!r.ok) throw new Error(await r.text());
  const rows = (await r.json()) as OpportunityRow[];
  return rows.map(normaliseRow);
}

/**
 * Paginated variant — returns the full envelope so the caller knows `total`
 * and `has_more` for virtualised tables.
 */
export async function getBrandOpportunitiesPaginated(
  brandId: string,
  query: OpportunityQuery = {},
): Promise<OpportunityListResponse> {
  const params = new URLSearchParams(buildOpportunityQuery(query).replace(/^\?/, ""));
  params.set("paginated", "true");
  const r = await apiFetch(
    `/api/v1/brands/${encodeURIComponent(brandId)}/opportunities?${params.toString()}`,
  );
  if (!r.ok) throw new Error(await r.text());
  const env = (await r.json()) as OpportunityListResponse;
  return {
    ...env,
    items: env.items.map(normaliseRow),
  };
}

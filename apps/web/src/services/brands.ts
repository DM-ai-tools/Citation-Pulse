import { apiFetch } from "./apiClient";
import type { OpportunityRow } from "@/types/report";

/** Open (or other) gap opportunity rows for dashboard / brand views. */
export async function getBrandOpportunities(brandId: string, status = "open"): Promise<OpportunityRow[]> {
  const r = await apiFetch(
    `/api/v1/brands/${encodeURIComponent(brandId)}/opportunities?status=${encodeURIComponent(status)}`,
  );
  if (!r.ok) throw new Error(await r.text());
  const rows = (await r.json()) as OpportunityRow[];
  return rows.map((o) => ({
    ...o,
    detected_at: o.detected_at == null ? null : String(o.detected_at),
  }));
}

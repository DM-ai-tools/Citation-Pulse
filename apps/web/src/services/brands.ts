import { buildGapAnalysisFromOpportunities } from "@/lib/gapAnalysisFallback";
import { apiFetch } from "./apiClient";
import type { GapAnalysisRow } from "@/types/gapsAnalysis";
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

/** Full gap analysis for dashboard (API route, with opportunities fallback). */
export async function getBrandGapsAnalysis(brandId: string): Promise<GapAnalysisRow[]> {
  const r = await apiFetch(`/api/v1/brands/${encodeURIComponent(brandId)}/gaps-analysis`);
  if (r.ok) {
    const rows = (await r.json()) as GapAnalysisRow[];
    return rows.map((row) => ({
      ...row,
      opportunity_id: String(row.opportunity_id),
      affected_engines: row.affected_engines ?? [],
      engine_breakdown: row.engine_breakdown ?? [],
    }));
  }

  // No analysis yet or brand not in workspace — try opportunities, else empty list.
  if (r.status === 404) {
    const oppRes = await apiFetch(
      `/api/v1/brands/${encodeURIComponent(brandId)}/opportunities?status=open`,
    );
    if (oppRes.ok) {
      const opportunities = (await oppRes.json()) as OpportunityRow[];
      return buildGapAnalysisFromOpportunities(
        opportunities.map((o) => ({
          ...o,
          detected_at: o.detected_at == null ? null : String(o.detected_at),
        })),
      );
    }
    return [];
  }

  const detail = await r.text().catch(() => "");
  throw new Error(detail || `Gaps request failed (${r.status})`);
}

import type { CompetitorDiscoveryResult } from "./competitors";
import type { ScanSnapshot } from "./scan";

export type GapItem = {
  prompt_id: string;
  score: number;
  reason: string;
  grade: string;
};

/**
 * Top Gap Opportunities row (from `opportunities` table via scan report payload).
 *
 * `demand_*` fields are populated by the weekly `refresh_demand` Celery job.
 * Older rows scanned before the job's first run may have these unset — UI
 * falls back to UNKNOWN pill + dash tooltip when so.
 */
export type OpportunityRow = {
  id: string;
  brand_id: string;
  prompt_id: string;
  title: string;
  gap_type: string;
  scope: string | null;
  grade: string;
  heat: string;
  opportunity_score: number;
  description: string;
  est_volume: number | null;
  status: string;
  detected_at: string | null;

  /** 0..1 — precomputed demand score (drives final opportunity_score). */
  demand_score?: number | null;
  /** Display pill bucket — high | medium | low | unknown. */
  demand_bucket?: string | null;
  /** Uppercase display copy: HIGH | MEDIUM | LOW | UNKNOWN. */
  demand_pill?: string | null;
  /** Which step of the 4-step fallback produced the value. */
  demand_source?: "literal" | "variant" | "internal" | "default" | string | null;
  /** Keyword variant that gave us the raw volume (variant source only). */
  demand_variant?: string | null;
  /** Raw monthly volume — TOOLTIP / DETAILS ONLY. Do NOT render in the row. */
  demand_raw_volume?: number | null;
  /** ISO timestamp the demand was last refreshed. */
  demand_refreshed_at?: string | null;
};

/** Envelope shape returned when calling /opportunities?paginated=true. */
export type OpportunityListResponse = {
  items: OpportunityRow[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

/** Query params for the brand opportunities API. */
export type OpportunityQuery = {
  status?: "open" | "snoozed" | "queued" | "resolved";
  grade?: "A" | "B" | "C";
  gap_type?:
    | "absent_all"
    | "competitor_dominant"
    | "engine_specific_gap"
    | "weak_engine"
    | "refresh_content"
    | "extend_presence";
  limit?: number;
  offset?: number;
};

export type ReportData = ScanSnapshot & {
  gaps: GapItem[];
  breakdown: {
    brand_share: number;
    competitor_share: number;
    third_party_share: number;
    neutral_share: number;
  } | null;
  competitors: { id: string; name: string; domains: string }[];
  /** Tiered AI competitor discovery (same-level + one-level-above), filled when scan completes. */
  competitor_discovery?: CompetitorDiscoveryResult | null;
  /** Graded gaps for this brand (open rows); empty until `detect_opportunities` has run. */
  opportunities?: OpportunityRow[];
  /** Embedded on scan report API — multi-entity SoV for funnel UIs (shape matches apps/web SoV types). */
  sov_multi_engine?: unknown;
  sov_multi_weekly_trend?: unknown;
};

export type EngineScore = { engine: string; score: number };

import type { ScanSnapshot } from "./scan";

export type GapItem = {
  prompt_id: string;
  score: number;
  reason: string;
  grade: string;
};

/** Top Gap Opportunities row (from `opportunities` table via scan report payload). */
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
  /** Graded gaps for this brand (open rows); empty until `detect_opportunities` has run. */
  opportunities?: OpportunityRow[];
};

export type EngineScore = { engine: string; score: number };

import type { MultiWeeklyResponse, SoVMultiEntityResponse } from "@/components/sov/BrandSovDashboard";
import type { CompetitorDiscoveryResult } from "./competitors";
import type { CompetitorCitationVisibility } from "./competitorVisibility";
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
  /** Tiered AI competitor discovery (filled when scan completes). */
  competitor_discovery?: CompetitorDiscoveryResult | null;
  /** True while background tiered discovery is still running (poll report until false). */
  competitor_discovery_pending?: boolean;
  competitor_discovery_status?: string | null;
  /** Competitor landscape matched to live engine citations, ranked by visibility. */
  competitor_citation_visibility?: CompetitorCitationVisibility | null;
  /** Domains the user entered at scan setup. */
  user_provided_competitors?: {
    domain: string;
    name: string;
    level: string;
    tier?: string;
    source?: string;
  }[];
  /** Competitors returned by AI discovery (same-level + one tier above). */
  analysis_competitors?: {
    domain: string;
    name: string;
    level: string;
    tier?: string;
    rank?: number | null;
    source?: string;
  }[];
  /** Graded gaps for this brand (open rows); empty until `detect_opportunities` has run. */
  opportunities?: OpportunityRow[];
  /** Embedded on ``GET /scans/{id}/report`` so anonymous funnel pages do not call Clerk-protected ``/brands/.../sov``. */
  sov_multi_engine?: SoVMultiEntityResponse | null;
  sov_multi_weekly_trend?: MultiWeeklyResponse | null;
};

export type EngineScore = { engine: string; score: number };

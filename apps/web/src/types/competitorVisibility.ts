export type EngineCitationHit = {
  engine: string;
  url: string;
  ownership: string;
  position?: number | null;
  snippet?: string | null;
};

export type RankedCompetitorVisibility = {
  domain: string;
  name: string;
  tier: string;
  level?: string | null;
  discovery_rank?: number | null;
  visibility_rank: number;
  visibility_score: number;
  engine_count: number;
  citation_count: number;
  engines: string[];
  /** Engines that cited this competitor (subset of scan engines). */
  cited_engines?: string[];
  best_position?: number | null;
  matched_in_discovery: boolean;
  /** Listed by the user when the scan was created. */
  user_provided?: boolean;
  cited_by_engines: boolean;
  reasoning: string;
  authority_advantage?: string | null;
  discovery_citations: { type: string; url: string; evidence: string; relevance_score?: number | null }[];
  engine_citations: EngineCitationHit[];
  /** URLs from each engine that match this competitor's domain. */
  citations_by_engine?: Record<string, EngineCitationHit[]>;
  /** Best position per cited engine (API-computed). */
  cited_engines_detail?: { engine: string; position: number | null }[];
};

export type TierBalanceMeta = {
  same_tier_cited: number;
  one_above_tier_cited: number;
  same_tier_min: number;
  one_above_tier_min: number;
  same_tier_max: number;
  one_above_tier_max: number;
  tier_targets_met: boolean;
  missing_tiers: string[];
};

export type CompetitorCitationVisibility = {
  prompt_id?: string;
  prompt_text: string;
  engines: string[];
  /** All strict checks passed (2+2, each ≥2 AIs per prompt). */
  validation_complete?: boolean;
  display_ready?: boolean;
  ranked_competitors: RankedCompetitorVisibility[];
  /** Same as ranked_competitors — discovery + user-provided companies. */
  competitors?: RankedCompetitorVisibility[];
  user_provided_competitors?: { domain: string; name: string }[];
  user_provided_count?: number;
  discovery_matched_count: number;
  engine_cited_count: number;
  both_matched_count: number;
  discovery_only: RankedCompetitorVisibility[];
  other_cited_domains: RankedCompetitorVisibility[];
  /** Full ranked pool (cited + uncited) for merging display when tier slots are sparse. */
  all_ranked_competitors?: RankedCompetitorVisibility[];
  /** Per-prompt visibility when the scan has multiple prompts. */
  by_prompt?: CompetitorCitationVisibility[];
  tier_balance?: TierBalanceMeta;
  display_min_target?: number;
  display_max_limit?: number;
};

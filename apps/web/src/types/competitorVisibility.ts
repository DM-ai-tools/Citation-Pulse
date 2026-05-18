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
};

export type CompetitorCitationVisibility = {
  prompt_id?: string;
  prompt_text: string;
  engines: string[];
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
  /** Per-prompt visibility when the scan has multiple prompts. */
  by_prompt?: CompetitorCitationVisibility[];
};

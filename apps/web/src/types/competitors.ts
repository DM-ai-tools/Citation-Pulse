export type CompetitorCitation = {
  type: string;
  url: string;
  evidence: string;
  relevance_score?: number | null;
};

export type TargetCompanyAnalysis = {
  domain: string;
  name: string;
  detected_services: string[];
  detected_niche: string;
  detected_locations: string[];
  company_tier: string;
  tier_reasoning: string;
};

export type SameLevelCompetitor = {
  domain: string;
  name: string;
  tier: string;
  rank?: number | null;
  rank_reason?: string | null;
  similarity_score: number;
  citation_strength_score?: number | null;
  avg_position?: number | null;
  intersections?: number | null;
  reasoning: string;
  citations: CompetitorCitation[];
};

export type OneLevelAboveCompetitor = {
  domain: string;
  name: string;
  tier: string;
  rank?: number | null;
  rank_reason?: string | null;
  citation_strength_score?: number | null;
  authority_advantage: string;
  reasoning: string;
  citations: CompetitorCitation[];
};

export type DiscoveryValidationSummary = {
  same_level_validated: number;
  one_level_above_validated: number;
  citations_verified: boolean;
  excluded_domains_removed: boolean;
  notes: string;
};

export type CompetitorDiscoveryResult = {
  target_company: TargetCompanyAnalysis;
  same_level_competitors: SameLevelCompetitor[];
  one_level_above_competitors: OneLevelAboveCompetitor[];
  validation_summary?: DiscoveryValidationSummary | null;
};

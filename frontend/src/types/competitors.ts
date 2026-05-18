export type CompetitorCitation = {
  type: string;
  url: string;
  evidence: string;
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
  similarity_score: number;
  avg_position?: number | null;
  intersections?: number | null;
  reasoning: string;
  citations: CompetitorCitation[];
};

export type OneLevelAboveCompetitor = {
  domain: string;
  name: string;
  tier: string;
  authority_advantage: string;
  reasoning: string;
  citations: CompetitorCitation[];
};

export type CompetitorDiscoveryResult = {
  target_company: TargetCompanyAnalysis;
  same_level_competitors: SameLevelCompetitor[];
  one_level_above_competitors: OneLevelAboveCompetitor[];
};

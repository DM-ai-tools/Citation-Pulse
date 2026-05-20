export type GapAnalysisRow = {
  opportunity_id: string;
  title: string;
  short_label: string;
  grade: string;
  heat: string;
  gap_type: string;
  summary: string;
  detailed_explanation: string;
  why_it_matters: string;
  competitive_impact: string;
  suggested_direction: string;
  affected_engines: string[];
  engine_breakdown: string[];
  est_volume: number | null;
  opportunity_score: number;
};

import type { ScanSnapshot } from "./scan";

export type GapItem = {
  prompt_id: string;
  score: number;
  reason: string;
  grade: string;
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
};

export type EngineScore = { engine: string; score: number };

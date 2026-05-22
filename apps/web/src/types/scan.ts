import type { CompetitorDiscoveryResult } from "@/types/competitors";

export type EngineKey = "chatgpt" | "perplexity" | "gemini" | "claude";

export type CellStatus = "queued" | "running" | "cited" | "comp" | "none" | "error";

export type CellCitation = {
  url: string;
  ownership: "brand" | "competitor" | "neutral" | string;
  position: number | null;
  snippet: string | null;
};

export type MatrixCell = {
  promptId: string;
  engine: string;
  status: CellStatus;
  /** When ``status`` is ``cited``: 1-based rank of the best (earliest) brand URL in the engine's citation list (``1`` = first / "top"). */
  position?: number;
  /** ``top`` | ``lower`` — matches gap classifier ``CITED_TOP`` / ``CITED_LOWER`` (API may omit on older snapshots). */
  brandTier?: "top" | "lower";
  /** Total citations returned by this engine for this prompt (may be > citations.length). */
  citationsCount?: number;
  /** Top citations (max 8), pre-sorted brand > competitor > neutral. */
  citations?: CellCitation[];
  /** Present when the engine run failed (HTTP/provider error, missing key, etc.). */
  errorMessage?: string | null;
};

export type ScanSnapshot = {
  scan_id: string;
  status: string;
  /** ISO-8601 when scan finished (from API). */
  completed_at?: string | null;
  submitted_url: string;
  locale: string;
  engines: string[];
  score_overall: number | null;
  share_public?: boolean;
  share_token?: string | null;
  brand: { id: string; name: string; domains: string[] } | null;
  prompts: { id: string; text: string; locale: string }[];
  matrix: { cells: MatrixCell[] };
  progress: { per_engine: Record<string, { done: number; total: number }> };
  competitor_discovery?: CompetitorDiscoveryResult | null;
  competitor_discovery_pending?: boolean;
  competitor_discovery_status?: string | null;
  user_provided_competitors?: {
    domain: string;
    name: string;
    level: string;
    tier?: string;
    source?: string;
  }[];
  analysis_competitors?: {
    domain: string;
    name: string;
    level: string;
    tier?: string;
    rank?: number | null;
    source?: string;
  }[];
  competitors?: { id: string; name: string; domains: string }[];
};

export type ScanEvent =
  | { type: "engine.progress"; engine: string; done: number; total: number }
  | {
      type: "cell.update";
      promptId: string;
      engine: string;
      status: CellStatus;
      position?: number;
      citationsCount?: number;
      citations?: CellCitation[];
      errorMessage?: string | null;
    }
  | { type: "scan.eta"; etaSeconds: number }
  | { type: "scan.completed"; score: number }
  | { type: "competitor.discovery.started" }
  | { type: "competitor.discovery.ready" };

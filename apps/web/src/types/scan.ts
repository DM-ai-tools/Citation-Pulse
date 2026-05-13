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
  position?: number;
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
  | { type: "scan.completed"; score: number };

/** UI labels aligned with product mockups (Traffic Radius CitationPulse). */

export const ENGINE_SHORT: Record<string, string> = {
  chatgpt: "C",
  perplexity: "P",
  claude: "A",
  gemini: "G",
};

export const ENGINE_LABEL: Record<string, string> = {
  chatgpt: "ChatGPT",
  perplexity: "Perplexity",
  claude: "Claude",
  gemini: "Gemini",
};

/** Second line under engine name in live matrix header (matches processing mock). */
export const ENGINE_COLUMN_SUB: Record<string, string> = {
  chatgpt: "OpenAI",
  claude: "Anthropic",
  perplexity: "Sonar",
  gemini: "Google",
};

export function engineLetter(engine: string) {
  return ENGINE_SHORT[engine] ?? engine.slice(0, 1).toUpperCase();
}

export function engineTitle(engine: string) {
  // Legacy matrix rows only — product scans do not run Google AIO.
  if (engine === "google_aio") return "AI Overviews";
  return ENGINE_LABEL[engine] ?? engine;
}

/** Compact engine name for prompt-stream chips (matches HTML mock). */
export function engineStreamLabel(engine: string) {
  return engineTitle(engine);
}

/** Per-engine title on live scan progress rows. */
export function engineScanRowTitle(engine: string) {
  if (engine === "claude") return "Claude (Anthropic)";
  return engineTitle(engine);
}

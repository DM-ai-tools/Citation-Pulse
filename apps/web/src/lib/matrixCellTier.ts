import type { MatrixCell } from "@/types/scan";

/**
 * Matches API ``citation_states.BRAND_TOP_MAX_ZERO_BASED_POSITION``:
 * UI positions 1–3 (0-based ranks 0–2) are "top"; 4+ are "lower".
 */
export const BRAND_TOP_MAX_UI_POSITION = 3;

export const HEATMAP_SCENARIO_LEGEND = [
  { swatch: "bg-[#1FB36B]", label: "Brand cited (top)" },
  { swatch: "bg-[#8EE5B7]", label: "Brand cited (lower)" },
  { swatch: "bg-tr-landingOrange", label: "Competitor cited only" },
  { swatch: "bg-[#E74C3C]", label: "Brand & comp absent" },
] as const;

export const GRADE_SCENARIO_LEGEND = [
  {
    swatch: "bg-rose-400",
    label: "HOT · A — fix first",
    hint: "No brand citation (heatmap red) or competitors cited instead of you",
  },
  {
    swatch: "bg-amber-400",
    label: "WARM · B — plan next",
    hint: "Cited on some engines but weak or missing on one",
  },
  {
    swatch: "bg-cyan-400",
    label: "COOL · C — track later",
    hint: "Partial visibility — grow coverage over time",
  },
] as const;

/** True when a cited cell is top-tier (aligned with gap classifier ``CITED_TOP``). */
export function isBrandCitedTop(cell: MatrixCell | undefined): boolean {
  if (!cell || cell.status !== "cited") return false;
  if (cell.brandTier === "top") return true;
  if (cell.brandTier === "lower") return false;
  const p = cell.position;
  if (p == null || !Number.isFinite(p)) return false;
  return p <= BRAND_TOP_MAX_UI_POSITION;
}

export function isBrandCitedLower(cell: MatrixCell | undefined): boolean {
  return cell?.status === "cited" && !isBrandCitedTop(cell);
}

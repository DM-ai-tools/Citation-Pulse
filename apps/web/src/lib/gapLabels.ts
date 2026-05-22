import { engineTitle } from "@/lib/engineDisplay";
import type { GapAnalysisRow } from "@/types/gapsAnalysis";
import type { OpportunityRow } from "@/types/report";

function truncate(text: string, max: number): string {
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1).trim()}…`;
}

/** True when stored title is empty or accidentally heat/grade metadata. */
function promptTitleIsUsable(title: string, row: OpportunityRow): boolean {
  const t = title.trim();
  if (!t || t.length < 3) return false;
  const heat = (row.heat || "").trim().toUpperCase();
  const grade = (row.grade || "").trim().toUpperCase();
  const upper = t.toUpperCase();
  if (heat && upper === heat) return false;
  if (grade && upper === grade) return false;
  if (heat && grade && (upper === `${heat} · ${grade}` || upper === `${heat} ${grade}`)) return false;
  if (/^(HOT|WARM|COOL)$/i.test(t)) return false;
  if (/^[ABC]$/i.test(t)) return false;
  return true;
}

/** Scan-friendly one-line label (never heat/grade alone). */
export function gapShortLabel(row: OpportunityRow): string {
  const engine = row.scope ? engineTitle(row.scope) : null;
  switch (row.gap_type) {
    case "absent_all":
      return "Absent across AI engines";
    case "competitor_dominant":
      return "Competitor-led visibility";
    case "engine_specific_gap":
      return engine ? `Missing on ${engine}` : "Engine-specific visibility gap";
    case "weak_engine":
      return engine ? `Weak presence on ${engine}` : "Weak engine visibility";
    case "refresh_content":
      return engine ? `Visibility lost on ${engine}` : "Citation refresh needed";
    case "extend_presence":
      return engine ? `Extend presence on ${engine}` : "Partial engine coverage";
    default:
      return "Visibility gap";
  }
}

/** Primary heading for gap rows on report + dashboard. */
export function gapDisplayTitle(row: OpportunityRow, maxLen = 120): string {
  const prompt = row.title?.trim() || "";
  let label = promptTitleIsUsable(prompt, row) ? prompt : gapShortLabel(row);
  if (promptTitleIsUsable(prompt, row) && row.scope) {
    const eng = engineTitle(row.scope);
    if (!label.toLowerCase().includes(eng.toLowerCase())) {
      label = `${label} · ${eng}`;
    }
  }
  return truncate(label, maxLen);
}

export function gapDisplayDescription(row: OpportunityRow): string {
  const d = row.description?.trim();
  if (d) return d;
  return gapShortLabel(row);
}

/** Maps gap type to the heatmap scenario the grade reflects (for tooltips / a11y). */
export function gapScenarioHint(row: OpportunityRow): string {
  switch (row.gap_type) {
    case "absent_all":
      return "Priority: fix first — brand not cited on any engine (red heatmap)";
    case "competitor_dominant":
      return "Priority: fix first — competitors cited, your brand is not";
    case "engine_specific_gap":
      return "Plan next — strong on most engines, one engine still missing";
    case "weak_engine":
      return "Plan next — competitors show on at least one engine";
    case "refresh_content":
      return "Fix first — visibility lost on this engine vs prior run";
    case "extend_presence":
      return "Track later — cited on some engines; extend to the rest";
    default:
      return "Graded from prompt × engine visibility vs heatmap";
  }
}

export function gapDisplayTitleFromAnalysis(row: GapAnalysisRow, maxLen = 120): string {
  const short = row.short_label?.trim();
  if (short && !/^(HOT|WARM|COOL)(\s|·|$)/i.test(short)) {
    return truncate(short, maxLen);
  }
  const asOpp: OpportunityRow = {
    id: row.opportunity_id,
    brand_id: "",
    prompt_id: "",
    title: row.title?.trim() || "",
    gap_type: row.gap_type,
    scope: null,
    grade: row.grade,
    heat: row.heat,
    opportunity_score: row.opportunity_score,
    description: row.summary,
    est_volume: row.est_volume,
    status: "open",
    detected_at: null,
  };
  return gapDisplayTitle(asOpp, maxLen);
}

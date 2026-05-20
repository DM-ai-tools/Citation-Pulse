import { engineTitle } from "@/lib/engineDisplay";
import type { OpportunityRow } from "@/types/report";

/** Scan-friendly one-line label for main UI (no full prompt text). */
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
      return row.heat ? `${row.heat} priority gap` : "Visibility gap";
  }
}

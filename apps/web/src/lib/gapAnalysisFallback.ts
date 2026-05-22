import { gapDisplayTitle, gapShortLabel } from "@/lib/gapLabels";
import { engineTitle } from "@/lib/engineDisplay";
import type { GapAnalysisRow } from "@/types/gapsAnalysis";
import type { OpportunityRow } from "@/types/report";

function snippet(text: string, max = 100): string {
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1).trim()}…`;
}

function gradeNote(grade: string): string {
  if (grade === "A") return "Priority: address in the current sprint.";
  if (grade === "B") return "Priority: schedule right after HOT gaps.";
  return "Priority: monitor; tackle after higher-impact gaps close.";
}

function buildCopy(row: OpportunityRow) {
  const q = snippet(row.title, 110);
  const eng = row.scope ? engineTitle(row.scope) : null;
  const summary = row.description?.trim() || "";

  let detailed = "";
  let why = "";
  let impact = "";
  let direction = "";

  switch (row.gap_type) {
    case "absent_all":
      detailed = `For “${q}”, your brand is absent across the engines we track. ${summary}`;
      why = `Shoppers researching “${snippet(row.title, 60)}” may never see your brand in the AI answer they trust.`;
      impact = "Rivals and publishers can occupy every citation slot for this query.";
      direction = `Publish a definitive resource for this intent and earn placements on domains already cited for similar searches. ${gradeNote(row.grade)}`;
      break;
    case "competitor_dominant":
      detailed = `For “${q}”, competitors dominate citations while your brand is missing. ${summary}`;
      why = `“${snippet(row.title, 55)}” currently routes buyer trust to rivals in AI summaries.`;
      impact = "Multiple competitor domains share the cite pool; you are not in the shortlist.";
      direction = `Add a head-to-head comparison page and pursue backlinks from sources rivals already use. ${gradeNote(row.grade)}`;
      break;
    case "engine_specific_gap":
      detailed = eng
        ? `For “${q}”, you are cited on most engines but not on ${eng}. ${summary}`
        : `For “${q}”, one engine still omits your brand. ${summary}`;
      why = eng
        ? `Buyers who start on ${eng} for “${snippet(row.title, 50)}” will not discover you.`
        : `A single-engine blind spot caps reach for this prompt.`;
      impact = eng
        ? `${eng} answers for this query surface competitor or third-party sources instead of you.`
        : "Competitors capture discovery on the engine where you are absent.";
      direction = eng
        ? `Create ${eng}-specific FAQs and earn 2–3 trusted citations for “${snippet(row.title, 45)}”. ${gradeNote(row.grade)}`
        : `Close the open engine with targeted content and outreach. ${gradeNote(row.grade)}`;
      break;
    case "weak_engine":
      detailed = eng
        ? `For “${q}”, your cite on ${eng} is weaker than rivals. ${summary}`
        : `For “${q}”, visibility is soft on a key engine. ${summary}`;
      why = eng
        ? `On ${eng}, “${snippet(row.title, 50)}” ranks others above you — often read as “not recommended.”`
        : `Soft ranking reduces clicks even when you appear.`;
      impact = eng
        ? `Competitor pages outrank yours in ${eng}'s citation list for this exact question.`
        : "Rivals appear more authoritative for this intent.";
      direction = eng
        ? `Refresh the ranking URL, add expert proof, and secure mentions ${eng} already trusts. ${gradeNote(row.grade)}`
        : `Strengthen authority signals on the weak engine. ${gradeNote(row.grade)}`;
      break;
    case "refresh_content":
      detailed = eng
        ? `For “${q}”, you recently dropped off ${eng}. ${summary}`
        : `For “${q}”, a previous cite appears to have been lost. ${summary}`;
      why = eng
        ? `A lost cite on ${eng} for “${snippet(row.title, 50)}” signals you are no longer the default answer.`
        : "Returning buyers may assume a competitor replaced you.";
      impact = eng
        ? `Another domain likely took the top position on ${eng} for this prompt.`
        : "Share shifts to whoever now owns the freshest cite.";
      direction = eng
        ? `Audit what changed on ${eng}, update the winning page, and reclaim backlinks. ${gradeNote(row.grade)}`
        : `Refresh content and re-earn citations for this query. ${gradeNote(row.grade)}`;
      break;
    case "extend_presence":
      detailed = eng
        ? `For “${q}”, coverage is incomplete — still open on ${eng}. ${summary}`
        : `For “${q}”, you have partial engine coverage. ${summary}`;
      why = eng
        ? `Prospects using ${eng} for “${snippet(row.title, 50)}” still miss your brand.`
        : "Patchy coverage leaves holes in the buyer journey.";
      impact = eng
        ? `Open engines (including ${eng}) send this query's traffic elsewhere.`
        : "Each open engine is share you do not capture.";
      direction = eng
        ? `Prioritize ${eng}: ship a focused landing page and pitch publishers cited in live answers. ${gradeNote(row.grade)}`
        : `Close the remaining open engines with targeted pages. ${gradeNote(row.grade)}`;
      break;
    default:
      detailed = `For “${q}”, visibility is uneven. ${summary}`;
      why = `“${snippet(row.title, 60)}” exposes a gap in how AI models cite your brand.`;
      impact = "Competitors or publishers may own the citations you lack.";
      direction = `Improve proof points and third-party mentions for this prompt. ${gradeNote(row.grade)}`;
  }

  return { detailed, why, impact, direction };
}

/** Client-side analysis when `/gaps-analysis` is unavailable (unique per row). */
export function buildGapAnalysisFromOpportunities(rows: OpportunityRow[]): GapAnalysisRow[] {
  return rows.map((row) => {
    const promptRaw = row.title?.trim() || "";
    const title = gapDisplayTitle(row, 512);
    const copy = buildCopy(row);
    return {
      opportunity_id: row.id,
      title: promptRaw.length > 512 ? `${promptRaw.slice(0, 509)}…` : promptRaw || title,
      short_label: gapShortLabel(row),
      grade: row.grade,
      heat: row.heat,
      gap_type: row.gap_type,
      summary: row.description,
      detailed_explanation: copy.detailed,
      why_it_matters: copy.why,
      competitive_impact: copy.impact,
      suggested_direction: copy.direction,
      affected_engines: row.scope ? [engineTitle(row.scope)] : [],
      engine_breakdown: row.scope
        ? [`${engineTitle(row.scope)}: ${row.description}`]
        : [],
      est_volume: row.est_volume,
      opportunity_score: row.opportunity_score,
    };
  });
}

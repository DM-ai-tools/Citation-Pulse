import type { CompetitorRosterItem } from "@/components/report/CompetitorRoster";
import type { ReportData } from "@/types/report";

export function rosterFromReport(data: ReportData): {
  userProvided: CompetitorRosterItem[];
  analysis: CompetitorRosterItem[];
} {
  const userProvided: CompetitorRosterItem[] = (data.user_provided_competitors ?? []).map((r) => ({
    domain: r.domain,
    name: r.name,
    level: r.level || "user_provided",
    tier: r.tier,
    source: "user" as const,
  }));

  const analysis: CompetitorRosterItem[] = (data.analysis_competitors ?? []).map((r) => ({
    domain: r.domain,
    name: r.name,
    level: r.level,
    tier: r.tier,
    rank: r.rank ?? null,
    source: "analysis" as const,
  }));

  return { userProvided, analysis };
}

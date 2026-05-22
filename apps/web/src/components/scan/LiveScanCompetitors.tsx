"use client";

import { CompetitorRoster } from "@/components/report/CompetitorRoster";
import { Spinner } from "@/components/primitives";
import { rosterFromReport } from "@/lib/competitorRoster";
import type { ScanSnapshot } from "@/types/scan";
import type { ReportData } from "@/types/report";

export function LiveScanCompetitors({ data }: { data: ScanSnapshot }) {
  const pending = Boolean(data.competitor_discovery_pending);
  const discovery = data.competitor_discovery;
  const roster = rosterFromReport(data as ReportData);
  const hasRoster = roster.userProvided.length > 0 || roster.analysis.length > 0;

  if (!pending && !discovery && !hasRoster) {
    return null;
  }

  return (
    <section className="rounded-[18px] border border-tr-line bg-white p-6 shadow-[0_12px_40px_rgba(10,37,64,0.08)]">
      <h3 className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">
        Competitor landscape
      </h3>
      <p className="mt-1 text-[12px] text-tr-mute">
        Discovered while engines run — full analysis continues on your report.
      </p>

      {pending && !discovery ? (
        <div className="mt-4 flex items-center gap-3 text-[13px] text-tr-navy" role="status">
          <Spinner className="h-5 w-5 shrink-0 text-brand-primary" />
          Building competitor list…
        </div>
      ) : null}

      {hasRoster ? (
        <div className="mt-4 max-h-[240px] overflow-y-auto pr-1">
          <CompetitorRoster
            analysis={roster.analysis}
            userProvided={roster.userProvided}
            variant="report"
          />
        </div>
      ) : discovery ? (
        <p className="mt-4 text-[12px] text-tr-mute">
          Found{" "}
          <strong className="text-tr-navy">
            {(discovery.same_level_competitors?.length ?? 0) +
              (discovery.one_level_above_competitors?.length ?? 0)}
          </strong>{" "}
          competitors — open the full report for tiered cards and citations.
        </p>
      ) : null}
    </section>
  );
}

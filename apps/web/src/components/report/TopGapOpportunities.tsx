"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { CitationScenarioLegend } from "@/components/report/CitationScenarioLegend";
import { gapDisplayDescription, gapDisplayTitle, gapScenarioHint } from "@/lib/gapLabels";
import type { OpportunityRow } from "@/types/report";

function gradeBadgeClass(grade: string) {
  if (grade === "A") return "bg-sky-100 text-[#0c4a6e]";
  if (grade === "B") return "bg-sky-100/90 text-[#0c4a6e]";
  return "bg-cyan-50 text-[#0e7490]";
}

function heatPillClass(grade: string) {
  if (grade === "A") return "bg-rose-100 text-rose-800 ring-1 ring-rose-200/80";
  if (grade === "B") return "bg-amber-100 text-amber-900 ring-1 ring-amber-200/80";
  return "bg-cyan-100 text-cyan-900 ring-1 ring-cyan-200/80";
}

function formatMonthlySearches(v: number | null | undefined): string {
  if (v == null || typeof v !== "number" || !Number.isFinite(v) || v <= 0) return "—";
  if (v >= 1_000_000) {
    const m = v / 1_000_000;
    const s = (m >= 10 ? Math.round(m) : Math.round(m * 10) / 10).toString();
    return `${s.replace(/\.0$/, "")}M`;
  }
  if (v >= 1000) {
    const k = v / 1000;
    const s = (k >= 10 ? Math.round(k) : Math.round(k * 10) / 10).toString();
    return `${s.replace(/\.0$/, "")}k`;
  }
  return String(Math.round(v));
}

function OpportunitiesLegendFootnote({
  gapsHref,
  gapCount,
  showGapsLink = true,
}: {
  gapsHref: string;
  gapCount: number;
  showGapsLink?: boolean;
}) {
  return (
    <div className="border-t border-tr-line bg-tr-pale/35 px-[22px] py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <CitationScenarioLegend variant="grades" title="How to read grades" className="min-w-0 flex-1" />
        {showGapsLink ? (
          <Link
            href={gapsHref}
            className="shrink-0 font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-navy underline decoration-tr-line underline-offset-2 hover:text-brand-primary"
          >
            View details ({gapCount})
          </Link>
        ) : null}
      </div>
    </div>
  );
}

/** Summary on the report; full gaps UI lives at `/report/[scanId]/gaps`. */
export function TopGapOpportunities({
  opportunities,
  scanId,
  className,
  id,
}: {
  opportunities: OpportunityRow[];
  /** When set, shows link to full gaps page. */
  scanId?: string;
  className?: string;
  id?: string;
}) {
  const rows = Array.isArray(opportunities) ? opportunities : [];
  const gapsHref = scanId ? `/report/${encodeURIComponent(scanId)}/gaps` : "#";

  return (
    <section
      id={id}
      data-testid="top-gap-opportunities"
      className={cn(
        "overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]",
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-tr-line px-[22px] py-[18px]">
        <h3 className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">
          Top gap opportunities
        </h3>
        <p className="text-xs text-tr-mute">graded by impact</p>
      </div>

      {rows.length === 0 ? (
        <p className="px-[22px] py-10 text-center text-[13px] leading-relaxed text-tr-mute">
          No graded gaps for this scan yet — the API builds this list when the scan finishes.
        </p>
      ) : (
        <>
          <ul className="divide-y divide-tr-line">
            {rows.map((row) => (
              <li
                key={row.id}
                className="flex flex-wrap items-start gap-3 px-[22px] py-4 sm:flex-nowrap sm:gap-4"
                data-testid="gap-summary-row"
              >
                <div
                  className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg font-display text-base font-black",
                    gradeBadgeClass(row.grade),
                  )}
                  title={gapScenarioHint(row)}
                >
                  {row.grade}
                </div>
                <div className="min-w-0 flex-1 basis-[min(100%,16rem)] sm:basis-auto">
                  <p
                    className="font-display text-[14.5px] font-bold leading-snug text-tr-navy"
                    title={row.title?.trim() || undefined}
                  >
                    {gapDisplayTitle(row)}
                  </p>
                  <p className="mt-1 text-[12.5px] leading-relaxed text-tr-mute">{gapDisplayDescription(row)}</p>
                </div>
                <div className="ml-auto flex shrink-0 items-start gap-4 sm:ml-0">
                  <div className="text-right">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-tr-mute">
                      Est. monthly searches
                    </p>
                    <p className="mt-0.5 font-display text-[15px] font-black tabular-nums text-tr-navy">
                      {formatMonthlySearches(row.est_volume)}
                    </p>
                  </div>
                  <div className="pt-0.5">
                    <span
                      className={cn(
                        "inline-flex rounded-full px-2.5 py-1 font-display text-[10.5px] font-extrabold uppercase tracking-wide",
                        heatPillClass(row.grade),
                      )}
                      title={gapScenarioHint(row)}
                    >
                      {row.heat} · {row.grade}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
          <OpportunitiesLegendFootnote gapsHref={gapsHref} gapCount={rows.length} showGapsLink={Boolean(scanId)} />
        </>
      )}
    </section>
  );
}

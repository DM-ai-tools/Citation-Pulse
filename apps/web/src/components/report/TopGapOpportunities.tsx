"use client";

import { cn } from "@/lib/utils";
import { engineTitle } from "@/lib/engineDisplay";
import type { OpportunityRow } from "@/types/report";

function rowTitle(row: OpportunityRow): string {
  const base = row.title?.trim() || "(prompt)";
  if (row.scope) {
    return `${base} · ${engineTitle(row.scope)}`;
  }
  return base;
}

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

export function TopGapOpportunities({
  opportunities,
  className,
}: {
  opportunities: OpportunityRow[];
  className?: string;
}) {
  const rows = opportunities ?? [];

  return (
    <section
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
          No graded gaps for this scan yet — the API builds this list when the scan finishes (and again on each report
          load if it was still empty). If you still see this after a <strong className="font-semibold text-tr-navy">completed</strong>{" "}
          scan, your prompts may not match any gap pattern (e.g. brand cited across engines). Nightly jobs still
          refresh scores for dashboards.
        </p>
      ) : (
        <ul className="divide-y divide-tr-line">
          {rows.map((row) => (
            <li key={row.id} className="flex items-start gap-3 px-[22px] py-4 sm:gap-4">
              <div
                className={cn(
                  "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg font-display text-base font-black",
                  gradeBadgeClass(row.grade),
                )}
                aria-hidden
              >
                {row.grade}
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-display text-[14.5px] font-bold leading-snug text-tr-navy">{rowTitle(row)}</p>
                <p className="mt-1 text-[12.5px] leading-relaxed text-tr-mute">{row.description}</p>
              </div>
              <div className="shrink-0 pt-0.5">
                <span
                  className={cn(
                    "inline-flex rounded-full px-2.5 py-1 font-display text-[10.5px] font-extrabold uppercase tracking-wide",
                    heatPillClass(row.grade),
                  )}
                >
                  {row.heat} · {row.grade}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

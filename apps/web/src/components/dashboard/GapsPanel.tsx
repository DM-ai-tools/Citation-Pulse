"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { ErrorState, Skeleton } from "@/components/primitives";
import { buildGapAnalysisFromOpportunities } from "@/lib/gapAnalysisFallback";
import { gapDisplayTitleFromAnalysis } from "@/lib/gapLabels";
import { getBrandGapsAnalysis } from "@/services/brands";
import type { GapAnalysisRow } from "@/types/gapsAnalysis";
import type { ReportData } from "@/types/report";

function rowTitle(row: GapAnalysisRow): string {
  return gapDisplayTitleFromAnalysis(row);
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

const GRADE_LEGEND = [
  { swatch: "bg-rose-400", label: "HOT · A — fix first" },
  { swatch: "bg-amber-400", label: "WARM · B — plan next" },
  { swatch: "bg-cyan-400", label: "COOL · C — track later" },
] as const;

function AnalysisField({ label, children }: { label: string; children: string }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-tr-mute">{label}</p>
      <p className="mt-1 text-[13px] leading-relaxed text-tr-body">{children}</p>
    </div>
  );
}

function GapSummaryRow({ row }: { row: GapAnalysisRow }) {
  return (
    <li className="border-b border-tr-line px-[22px] py-4 last:border-b-0">
      <div className="flex flex-wrap items-start gap-3 sm:flex-nowrap sm:gap-4">
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
          <p className="mt-2 text-[13px] leading-relaxed text-tr-body">{row.summary}</p>
        </div>
      </div>
    </li>
  );
}

export function GapRow({ row }: { row: GapAnalysisRow }) {
  const [open, setOpen] = useState(false);

  return (
    <li className="border-b border-tr-line last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full flex-wrap items-start gap-3 px-[22px] py-4 text-left transition-colors hover:bg-tr-pale/30 sm:flex-nowrap sm:gap-4"
        aria-expanded={open}
      >
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg font-display text-base font-black",
            gradeBadgeClass(row.grade),
          )}
          aria-hidden
        >
          {row.grade}
        </div>
        <div className="min-w-0 flex-1 basis-[min(100%,16rem)] sm:basis-auto">
          <p className="font-display text-[14.5px] font-bold leading-snug text-tr-navy">{rowTitle(row)}</p>
          <p className="mt-1 text-[12.5px] leading-relaxed text-tr-mute">{row.summary}</p>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-3 sm:ml-0">
          <div className="hidden text-right sm:block">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-tr-mute">
              Est. monthly searches
            </p>
            <p className="mt-0.5 font-display text-[15px] font-black tabular-nums text-tr-navy">
              {formatMonthlySearches(row.est_volume)}
            </p>
          </div>
          <span
            className={cn(
              "inline-flex rounded-full px-2.5 py-1 font-display text-[10.5px] font-extrabold uppercase tracking-wide",
              heatPillClass(row.grade),
            )}
          >
            {row.heat} · {row.grade}
          </span>
          <ChevronDown
            className={cn("h-4 w-4 shrink-0 text-tr-mute transition-transform", open && "rotate-180")}
            aria-hidden
          />
        </div>
      </button>
      {open ? (
        <div className="space-y-4 border-t border-tr-line/80 bg-tr-pale/25 px-[22px] py-4 pl-[4.25rem] sm:pl-[5.5rem]">
          <AnalysisField label="What we found">{row.detailed_explanation}</AnalysisField>
          <AnalysisField label="Why it matters">{row.why_it_matters}</AnalysisField>
          <AnalysisField label="Competitive impact">{row.competitive_impact}</AnalysisField>
          <AnalysisField label="What to do">{row.suggested_direction}</AnalysisField>
          {row.affected_engines.length > 0 ? (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-tr-mute">
                Affected AI engines
              </p>
              <ul className="mt-1.5 flex flex-wrap gap-2">
                {row.affected_engines.map((e) => (
                  <li
                    key={e}
                    className="rounded-md border border-tr-line bg-white px-2.5 py-1 text-xs font-medium text-tr-navy"
                  >
                    {e}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {row.engine_breakdown.length > 0 ? (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-tr-mute">
                Per-engine visibility
              </p>
              <ul className="mt-1.5 list-inside list-disc text-[12px] text-tr-mute">
                {row.engine_breakdown.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

/** Unified gaps list: report-style rows + expandable analysis (dashboard / gaps page). */
export function GapsPanel({
  brandId,
  scanReport,
  summaryOnly = false,
}: {
  brandId?: string;
  scanReport?: ReportData;
  /** Title + description only (no expandable analysis). */
  summaryOnly?: boolean;
}) {
  const rowsFromScan = useMemo(
    () => (scanReport ? buildGapAnalysisFromOpportunities(scanReport.opportunities ?? []) : null),
    [scanReport],
  );

  const q = useQuery({
    queryKey: ["gaps-analysis", brandId],
    queryFn: () => getBrandGapsAnalysis(brandId!),
    enabled: Boolean(brandId) && !rowsFromScan,
    retry: 1,
  });

  const rows = rowsFromScan ?? (q.isSuccess ? q.data : null);
  const isPending = !rowsFromScan && q.isPending;
  const isError = !rowsFromScan && q.isError;
  const isSuccess = Boolean(rows?.length);

  return (
    <section
      data-testid="gaps-panel"
      className="overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-tr-line px-[22px] py-[18px]">
        <h2 className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">
          Gap opportunities
        </h2>
        <p className="text-xs text-tr-mute">
          {summaryOnly ? "gap title and description" : "click a row to expand details"}
        </p>
      </div>

      {isPending ? (
        <div className="space-y-0 px-[22px] py-6">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="mt-3 h-20 w-full" />
        </div>
      ) : null}

      {isError ? (
        <div className="px-[22px] py-6">
          <ErrorState message="Could not load gaps." onRetry={() => q.refetch()} />
        </div>
      ) : null}

      {!isPending && !isError && rows && rows.length === 0 ? (
        <p className="px-[22px] py-10 text-center text-[13px] leading-relaxed text-tr-mute">
          No open gaps detected yet. Run a scan or wait for gap detection to finish.
        </p>
      ) : null}

      {isSuccess && rows && rows.length > 0 ? (
        <>
          <ul className="list-none pl-0">
            {rows.map((row) =>
              summaryOnly ? (
                <GapSummaryRow key={row.opportunity_id} row={row} />
              ) : (
                <GapRow key={row.opportunity_id} row={row} />
              ),
            )}
          </ul>
          <div className="border-t border-tr-line bg-tr-pale/35 px-[22px] py-3">
            <div
              className="flex flex-wrap items-center gap-x-3.5 gap-y-2 rounded-[10px] border border-tr-line bg-white px-4 py-3 text-[11.5px] text-tr-body"
              role="list"
              aria-label="How to read grades"
            >
              <span className="font-display text-[10px] font-extrabold uppercase tracking-wide text-tr-navy">
                How to read grades
              </span>
              {GRADE_LEGEND.map((item) => (
                <span key={item.label} className="inline-flex items-center gap-1.5" role="listitem">
                  <span className={cn("h-3.5 w-3.5 shrink-0 rounded", item.swatch)} aria-hidden />
                  {item.label}
                </span>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

"use client";

import { cn } from "@/lib/utils";
import type { GapAnalysisRow } from "@/types/gapsAnalysis";

function rowTitle(row: GapAnalysisRow): string {
  const base = row.title?.trim() || "(prompt)";
  if (row.affected_engines.length === 1 && row.gap_type.includes("engine")) {
    const eng = row.affected_engines[0];
    if (!base.includes(eng)) return `${base} · ${eng}`;
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

function AnalysisField({ label, children }: { label: string; children: string }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-tr-mute">{label}</p>
      <p className="mt-1 text-[13px] leading-relaxed text-tr-body">{children}</p>
    </div>
  );
}

function GapDetailCard({ row }: { row: GapAnalysisRow }) {
  return (
    <article className="border-b border-tr-line px-[22px] py-6 last:border-b-0">
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
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="font-display text-[15px] font-bold leading-snug text-tr-navy">{rowTitle(row)}</p>
              <p className="mt-1 text-[12px] font-medium uppercase tracking-wide text-tr-mute">{row.short_label}</p>
            </div>
            <div className="flex shrink-0 items-center gap-4">
              <div className="text-right">
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
            </div>
          </div>
          <p className="mt-3 text-[13px] leading-relaxed text-tr-mute">{row.summary}</p>
        </div>
      </div>
      <div className="mt-5 space-y-4 border-t border-tr-line/80 pt-5 pl-0 sm:pl-[3.25rem]">
        <AnalysisField label="What we found">{row.detailed_explanation}</AnalysisField>
        <AnalysisField label="Why it matters">{row.why_it_matters}</AnalysisField>
        <AnalysisField label="Competitive impact">{row.competitive_impact}</AnalysisField>
        <AnalysisField label="What to do">{row.suggested_direction}</AnalysisField>
        {row.affected_engines.length > 0 ? (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-tr-mute">Affected AI engines</p>
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
            <p className="text-[10px] font-semibold uppercase tracking-wide text-tr-mute">Per-engine visibility</p>
            <ul className="mt-1.5 list-inside list-disc text-[12px] text-tr-mute">
              {row.engine_breakdown.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </article>
  );
}

export function GapAnalysisDetailView({ rows }: { rows: GapAnalysisRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="px-[22px] py-10 text-center text-[13px] leading-relaxed text-tr-mute">
        No gap analysis available for this scan.
      </p>
    );
  }

  return (
    <div data-testid="gap-analysis-detail-view">
      {rows.map((row) => (
        <GapDetailCard key={row.opportunity_id} row={row} />
      ))}
    </div>
  );
}

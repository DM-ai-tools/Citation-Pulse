"use client";

import { useState } from "react";
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

/** HIGH/MEDIUM/LOW demand pill — colour decoupled from grade so the user sees both signals. */
function demandPillClass(bucket: string | null | undefined) {
  const b = (bucket ?? "").toLowerCase();
  if (b === "high") return "bg-emerald-100 text-emerald-900 ring-1 ring-emerald-200/80";
  if (b === "medium") return "bg-amber-50 text-amber-900 ring-1 ring-amber-200/80";
  if (b === "low") return "bg-slate-100 text-slate-700 ring-1 ring-slate-200/80";
  return "bg-slate-50 text-slate-600 ring-1 ring-slate-200/70";
}

function demandPillLabel(row: OpportunityRow): string {
  if (row.demand_pill && row.demand_pill.trim()) return row.demand_pill;
  const b = (row.demand_bucket ?? "").toLowerCase();
  if (b === "high") return "HIGH";
  if (b === "medium") return "MEDIUM";
  if (b === "low") return "LOW";
  return "UNKNOWN";
}

/** Tooltip-only formatter: surface the raw monthly demand number. */
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

function demandSourceCopy(src: string | null | undefined): string {
  switch ((src ?? "").toLowerCase()) {
    case "literal":
      return "DataForSEO · prompt literal";
    case "variant":
      return "DataForSEO · keyword variant";
    case "internal":
      return "Internal composite (richness · consensus · crowd)";
    case "default":
      return "Default fallback (0.30)";
    default:
      return "Unknown";
  }
}

function DemandTooltip({ row }: { row: OpportunityRow }) {
  const rawVolume = formatMonthlySearches(row.demand_raw_volume ?? row.est_volume);
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute right-0 top-full z-20 mt-2 w-72 rounded-xl border border-tr-line bg-white p-3 text-left text-[12px] leading-relaxed text-tr-mute shadow-lift"
    >
      <p className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-navy">
        Demand details
      </p>
      <dl className="mt-2 space-y-1.5">
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-tr-mute">Raw monthly volume</dt>
          <dd className="font-mono text-[12px] text-tr-navy">{rawVolume}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-tr-mute">Source</dt>
          <dd className="text-[12px] text-tr-navy">{demandSourceCopy(row.demand_source)}</dd>
        </div>
        {row.demand_variant ? (
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-tr-mute">Variant used</dt>
            <dd className="max-w-[60%] truncate text-right font-mono text-[11px] text-tr-navy" title={row.demand_variant}>
              {row.demand_variant}
            </dd>
          </div>
        ) : null}
        {typeof row.demand_score === "number" ? (
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-tr-mute">Normalised score</dt>
            <dd className="font-mono text-[11px] text-tr-navy">{row.demand_score.toFixed(3)}</dd>
          </div>
        ) : null}
        {row.demand_refreshed_at ? (
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-tr-mute">Refreshed</dt>
            <dd className="text-[11px] text-tr-navy">{new Date(row.demand_refreshed_at).toLocaleDateString()}</dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}

function OpportunitiesLegendFootnote() {
  return (
    <div className="border-t border-tr-line bg-tr-pale/35 px-[22px] py-4">
      <p className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-navy">
        How to read grades
      </p>
      <p className="mt-2 text-[12px] leading-relaxed text-tr-mute">
        The <span className="font-semibold text-tr-navy">pill</span> on each row matches the tier. The{" "}
        <span className="font-semibold text-tr-navy">letter</span> in the square (A, B, or C) is the same priority level
        in short form. The model ranks from estimated monthly searches, how open the gap is across engines, competitor
        citations there, and how long the gap has persisted without closing.
      </p>
      <ul className="mt-3 list-none space-y-2.5 pl-0 text-[12px] leading-relaxed text-tr-mute">
        <li className="flex items-start gap-2.5 sm:gap-3">
          <span
            className={cn(
              "mt-0.5 shrink-0 rounded-full px-2 py-0.5 font-display text-[9.5px] font-extrabold uppercase tracking-wide sm:text-[10px]",
              heatPillClass("A"),
            )}
          >
            HOT · A
          </span>
          <span>
            Highest urgency: strong search upside and/or a sharp gap (for example absent on several engines or heavy
            competitor presence). Treat these prompts first in content and AI-visibility work.
          </span>
        </li>
        <li className="flex items-start gap-2.5 sm:gap-3">
          <span
            className={cn(
              "mt-0.5 shrink-0 rounded-full px-2 py-0.5 font-display text-[9.5px] font-extrabold uppercase tracking-wide sm:text-[10px]",
              heatPillClass("B"),
            )}
          >
            WARM · B
          </span>
          <span>
            Solid middle priority: meaningful demand or openness, but less extreme than A. Plan fixes on a near-term
            roadmap after the HOT rows.
          </span>
        </li>
        <li className="flex items-start gap-2.5 sm:gap-3">
          <span
            className={cn(
              "mt-0.5 shrink-0 rounded-full px-2 py-0.5 font-display text-[9.5px] font-extrabold uppercase tracking-wide sm:text-[10px]",
              heatPillClass("C"),
            )}
          >
            COOL · C
          </span>
          <span>
            Lower relative impact in this scoring pass. Still worth tracking; pick up after HOT and WARM unless your
            strategy targets these queries specifically.
          </span>
        </li>
      </ul>
    </div>
  );
}

function LoadingState() {
  return (
    <ul className="divide-y divide-tr-line" data-testid="top-gap-opportunities-loading">
      {Array.from({ length: 3 }).map((_, i) => (
        <li key={i} className="flex items-start gap-3 px-[22px] py-4 sm:gap-4">
          <div className="h-10 w-10 shrink-0 animate-pulse rounded-lg bg-tr-pale/70" />
          <div className="min-w-0 flex-1 space-y-2">
            <div className="h-3 w-2/3 animate-pulse rounded bg-tr-pale/70" />
            <div className="h-2.5 w-1/2 animate-pulse rounded bg-tr-pale/50" />
          </div>
          <div className="h-6 w-16 shrink-0 animate-pulse rounded-full bg-tr-pale/60" />
        </li>
      ))}
    </ul>
  );
}

function ErrorRetry({ onRetry, message }: { onRetry?: () => void; message?: string }) {
  return (
    <div className="px-[22px] py-8 text-center" data-testid="top-gap-opportunities-error">
      <p className="text-[13px] leading-relaxed text-tr-mute">
        {message ?? "Could not load Top Gap Opportunities. Check the API connection and try again."}
      </p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center rounded-md border border-tr-line bg-white px-3 py-1.5 font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-navy hover:bg-tr-pale/40"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function TopGapOpportunities({
  opportunities,
  className,
  id,
  isLoading = false,
  isError = false,
  errorMessage,
  onRetry,
}: {
  opportunities: OpportunityRow[];
  className?: string;
  /** Optional anchor id for in-page links (e.g. report hero CTA). */
  id?: string;
  /** Show skeleton rows while the query is fetching. */
  isLoading?: boolean;
  /** Render the retry state with a message + button. */
  isError?: boolean;
  errorMessage?: string;
  onRetry?: () => void;
}) {
  const rows = Array.isArray(opportunities) ? opportunities : [];
  const [openTooltip, setOpenTooltip] = useState<string | null>(null);

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

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorRetry onRetry={onRetry} message={errorMessage} />
      ) : rows.length === 0 ? (
        <p className="px-[22px] py-10 text-center text-[13px] leading-relaxed text-tr-mute">
          No graded gaps for this scan yet — the API builds this list when the scan finishes (and again on each report
          load if it was still empty). If you still see this after a <strong className="font-semibold text-tr-navy">completed</strong>{" "}
          scan, your prompts may not match any gap pattern (e.g. brand cited across engines). Nightly jobs still
          refresh scores for dashboards.
        </p>
      ) : (
        <ul className="divide-y divide-tr-line">
          {rows.map((row) => (
            <li
              key={row.id}
              className="flex flex-wrap items-start gap-3 px-[22px] py-4 sm:flex-nowrap sm:gap-4"
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
                <p className="mt-1 text-[12.5px] leading-relaxed text-tr-mute">{row.description}</p>
              </div>
              <div className="ml-auto flex shrink-0 items-start gap-3 sm:ml-0">
                {/*
                  Demand pill (HIGH/MEDIUM/LOW). The spec forbids rendering raw
                  search volume directly in the row UI — we keep the number in
                  the tooltip + `demand_raw_volume` field only.
                */}
                <div
                  className="relative"
                  onMouseEnter={() => setOpenTooltip(row.id)}
                  onMouseLeave={() => setOpenTooltip((cur) => (cur === row.id ? null : cur))}
                  onFocus={() => setOpenTooltip(row.id)}
                  onBlur={() => setOpenTooltip((cur) => (cur === row.id ? null : cur))}
                >
                  <button
                    type="button"
                    aria-describedby={`demand-tip-${row.id}`}
                    className={cn(
                      "inline-flex cursor-default items-center rounded-full px-2.5 py-1 font-display text-[10.5px] font-extrabold uppercase tracking-wide",
                      demandPillClass(row.demand_bucket),
                    )}
                  >
                    {demandPillLabel(row)}
                  </button>
                  {openTooltip === row.id ? (
                    <div id={`demand-tip-${row.id}`} className="pointer-events-auto">
                      <DemandTooltip row={row} />
                    </div>
                  ) : null}
                </div>
                <div className="pt-0.5">
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
            </li>
          ))}
        </ul>
      )}
      {!isLoading && !isError && rows.length > 0 ? <OpportunitiesLegendFootnote /> : null}
    </section>
  );
}

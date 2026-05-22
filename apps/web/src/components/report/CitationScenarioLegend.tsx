"use client";

import { cn } from "@/lib/utils";
import { GRADE_SCENARIO_LEGEND, HEATMAP_SCENARIO_LEGEND } from "@/lib/matrixCellTier";

type Variant = "heatmap" | "grades" | "both";

export function CitationScenarioLegend({
  variant = "heatmap",
  className,
  title,
}: {
  variant?: Variant;
  className?: string;
  title?: string;
}) {
  const showHeatmap = variant === "heatmap" || variant === "both";
  const showGrades = variant === "grades" || variant === "both";

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-3.5 gap-y-2 rounded-[10px] border border-tr-line bg-white px-4 py-3 text-[11.5px] text-tr-body",
        className,
      )}
      role="list"
      aria-label={title ?? "Citation scenarios"}
    >
      {title ? (
        <span className="w-full font-display text-[10px] font-extrabold uppercase tracking-wide text-tr-navy sm:w-auto">
          {title}
        </span>
      ) : null}
      {showHeatmap
        ? HEATMAP_SCENARIO_LEGEND.map((item) => (
            <span key={item.label} className="inline-flex items-center gap-1.5" role="listitem">
              <span className={cn("h-3.5 w-3.5 shrink-0 rounded", item.swatch)} aria-hidden />
              {item.label}
            </span>
          ))
        : null}
      {showGrades
        ? GRADE_SCENARIO_LEGEND.map((item) => (
            <span
              key={item.label}
              className="inline-flex items-center gap-1.5 text-tr-body"
              role="listitem"
              title={item.hint}
            >
              <span className={cn("h-3.5 w-3.5 shrink-0 rounded", item.swatch)} aria-hidden />
              {item.label}
            </span>
          ))
        : null}
    </div>
  );
}

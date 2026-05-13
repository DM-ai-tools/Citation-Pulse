"use client";

import { cn } from "@/lib/utils";
import { heatmapBreakdownCounts } from "@/lib/matrixStats";
import type { MatrixCell } from "@/types/scan";
import { engineTitle } from "@/lib/engineDisplay";

export function HeatmapBreakdownCards({
  cells,
  layer,
  promptCount,
  engineCount,
  citationScore,
}: {
  cells: MatrixCell[];
  layer?: string | null;
  promptCount?: number;
  engineCount?: number;
  citationScore?: number;
}) {
  const { brandTop, brandLower, comp, none, engineError, pct } = heatmapBreakdownCounts(cells);
  const cards = [
    {
      label: "BRAND CITED",
      sub: `${pct(brandTop)}%`,
      val: brandTop,
      wrap: "bg-[#1FB36B] text-white",
      numClass: "text-white",
      smallClass: "text-white/90",
    },
    {
      label: "LOWER POSITION",
      sub: `${pct(brandLower)}%`,
      val: brandLower,
      wrap: "bg-[#8EE5B7]",
      numClass: "text-[#14653e]",
      smallClass: "text-[#14653e]",
    },
    {
      label: "COMPETITOR ONLY",
      sub: `${pct(comp)}%`,
      val: comp,
      wrap: "bg-tr-landingOrange text-white",
      numClass: "text-white",
      smallClass: "text-white/90",
    },
    {
      label: "NOT VISIBLE",
      sub: `${pct(none)}%`,
      val: none,
      wrap: "bg-[#E74C3C] text-white",
      numClass: "text-white",
      smallClass: "text-white/90",
    },
    ...(engineError > 0
      ? [
          {
            label: "RUN FAILED",
            sub: `${pct(engineError)}%`,
            val: engineError,
            wrap: "border border-slate-400 bg-slate-600 text-white",
            numClass: "text-white",
            smallClass: "text-white/90",
          },
        ]
      : []),
  ];
  const layerName = layer ? engineTitle(layer).toUpperCase() : "ALL ENGINES";
  const headerMeta =
    typeof promptCount === "number" && typeof engineCount === "number"
      ? `${promptCount} prompts × ${engineCount} engines`
      : "";

  return (
    <div className="overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-tr-line px-[22px] py-[18px]">
        <h3 className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">
          Breakdown for &quot;{layerName}&quot;
          {headerMeta ? <span className="text-tr-mute"> · {headerMeta}</span> : null}
        </h3>
        {typeof citationScore === "number" && (
          <p className="text-xs text-tr-mute">
            Citation Score:{" "}
            <strong className="text-tr-navy">
              {citationScore} / 100
            </strong>
          </p>
        )}
      </div>
      <div
        className={cn(
          "grid gap-3 p-[22px] sm:grid-cols-2",
          cards.length > 4 ? "lg:grid-cols-3 xl:grid-cols-5" : "lg:grid-cols-4",
        )}
      >
        {cards.map((c) => (
          <div key={c.label} className={cn("rounded-xl px-4 py-5 text-center shadow-sm", c.wrap)}>
            <b className={cn("font-display text-[38px] font-black leading-none tabular-nums", c.numClass)}>
              {c.val}
            </b>
            <small className={cn("mt-1.5 block font-display text-[10.5px] font-extrabold uppercase tracking-wide", c.smallClass)}>
              {c.label} · {c.sub}
            </small>
          </div>
        ))}
      </div>
    </div>
  );
}

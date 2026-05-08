"use client";

import { useMemo, useState } from "react";
import { LiveScanHeatmapGrid } from "./LiveScanHeatmapGrid";
import { promptCompletionPct } from "@/lib/matrixStats";
import { cn } from "@/lib/utils";
import type { ScanSnapshot } from "@/types/scan";

function tabLabel(text: string, maxLen = 14) {
  const t = text.trim();
  if (t.length <= maxLen) return t;
  return `${t.slice(0, maxLen)}…`;
}

export function LiveCitationMatrix({ data }: { data: ScanSnapshot }) {
  const [tab, setTab] = useState<string | "all">("all");

  const allPct = useMemo(
    () => promptCompletionPct(data.prompts, data.engines, data.matrix.cells, null),
    [data],
  );

  const filteredPrompts = useMemo(() => {
    if (tab === "all") return data.prompts;
    return data.prompts.filter((p) => p.id === tab);
  }, [data.prompts, tab]);

  return (
    <div className="flex flex-col rounded-[18px] border border-tr-line bg-white px-5 pb-6 pt-5 shadow-[0_12px_40px_rgba(10,37,64,0.08)]">
      <div className="mb-3.5 flex flex-wrap items-baseline justify-between gap-2 border-b border-tr-line px-1 pb-3.5">
        <p className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">
          Live Citation Matrix
          <span className="ml-1.5 text-[11px] font-medium normal-case tracking-normal text-tr-mute">
            · prompts × engines
          </span>
        </p>
        <span className="animate-live-blink rounded bg-[#E74C3C] px-2.5 py-1 font-display text-[11px] font-extrabold uppercase tracking-wide text-white">
          Live
        </span>
      </div>

      <div className="mb-3.5 flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setTab("all")}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 font-display text-xs font-bold transition",
            tab === "all"
              ? "border-tr-navy bg-tr-navy text-white"
              : "border-tr-line bg-white text-tr-navy hover:border-brand-primary/40",
          )}
        >
          All prompts
          <span className={cn("text-[11px] font-semibold opacity-70", tab === "all" && "text-brand-primaryBright opacity-100")}>
            {allPct}%
          </span>
        </button>
        {data.prompts.map((p) => {
          const pct = promptCompletionPct(data.prompts, data.engines, data.matrix.cells, p.id);
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => setTab(p.id)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 font-display text-xs font-bold transition",
                tab === p.id
                  ? "border-tr-navy bg-tr-navy text-white"
                  : "border-tr-line bg-white text-tr-navy hover:border-brand-primary/40",
              )}
            >
              {tabLabel(p.text)}
              <span
                className={cn(
                  "text-[11px] font-semibold opacity-70",
                  tab === p.id && "text-brand-primaryBright opacity-100",
                )}
              >
                {pct}%
              </span>
            </button>
          );
        })}
      </div>

      <LiveScanHeatmapGrid prompts={filteredPrompts} engines={data.engines} cells={data.matrix.cells} />
    </div>
  );
}

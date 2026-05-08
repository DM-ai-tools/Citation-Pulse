"use client";

import { cn } from "@/lib/utils";
import { engineTitle } from "@/lib/engineDisplay";

function scoreTone(sc: number) {
  if (sc >= 60) return "bg-[rgba(31,179,107,0.18)] text-[#146d3e]";
  if (sc >= 40) return "bg-[rgba(248,165,27,0.18)] text-[#b87a14]";
  return "bg-[rgba(231,76,60,0.18)] text-[#b73121]";
}

export function EngineLayerSelector({
  engines,
  value,
  onChange,
  scores,
  hint = "Click an engine to change the heatmap layer",
}: {
  engines: string[];
  value: string | null;
  onChange: (e: string | null) => void;
  scores: Record<string, number>;
  hint?: string;
}) {
  return (
    <div className="rounded-[14px] border border-tr-line bg-white px-5 py-4 shadow-[0_8px_24px_rgba(10,37,64,0.06)]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:gap-5">
        <div className="flex shrink-0 flex-wrap items-center gap-3.5">
          <span className="font-display text-[10.5px] font-extrabold uppercase tracking-[1.2px] text-tr-teal">
            Engine layer
          </span>
          <span className="h-[3px] w-[22px] rounded-sm bg-brand-primary" />
          <span className="text-[12.5px] text-tr-mute">{hint}</span>
        </div>
        <div className="flex flex-1 flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onChange(null)}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg border-[1.5px] px-3.5 py-2 font-display text-[13px] font-bold transition",
              value === null
                ? "border-tr-navy bg-tr-navy text-white"
                : "border-tr-line bg-white text-tr-navy hover:border-brand-primary hover:text-brand-primary",
            )}
          >
            All layers
          </button>
          {engines.map((e) => {
            const sc = scores[e] ?? 0;
            const active = value === e;
            const tone = scoreTone(sc);
            return (
              <button
                key={e}
                type="button"
                onClick={() => onChange(e)}
                className={cn(
                  "inline-flex items-center gap-2 rounded-lg border-[1.5px] px-3.5 py-2 font-display text-[13px] font-bold transition",
                  active
                    ? "border-tr-navy bg-tr-navy text-white"
                    : "border-tr-line bg-white text-tr-navy hover:border-brand-primary hover:text-brand-primary",
                )}
              >
                {engineTitle(e)}
                <span
                  className={cn(
                    "rounded-xl px-2 py-0.5 font-display text-xs font-black tabular-nums",
                    active ? "bg-brand-primary text-tr-navy" : tone,
                  )}
                >
                  {sc}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

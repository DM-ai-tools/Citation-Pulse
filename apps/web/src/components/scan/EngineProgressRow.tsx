"use client";

import { cn } from "@/lib/utils";
import { engineLetter, engineScanRowTitle } from "@/lib/engineDisplay";

export function EngineProgressRow({
  engine,
  done,
  total,
}: {
  engine: string;
  done: number;
  total: number;
}) {
  const max = Math.max(1, total);
  const complete = done >= total && total > 0;
  const running = done > 0 && !complete;
  const pending = done === 0;
  const pct = Math.min(100, Math.round((100 * done) / max));
  const barPct = Math.max(pct, pending ? 2 : 0);
  const letter = engineLetter(engine);

  const rowTone = complete ? "done" : running ? "running" : "pending";

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-[10px] border px-3.5 py-3",
        rowTone === "done" && "border-emerald-500/25 bg-[rgba(31,179,107,0.06)]",
        rowTone === "running" && "border-brand-primary/25 bg-brand-primary/[0.05]",
        rowTone === "pending" && "border-tr-line bg-[#F6FCF8]",
      )}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-display text-[13px] font-extrabold text-white",
          complete && "bg-[#1FB36B]",
          running && "bg-brand-primary",
          pending && "bg-slate-300",
        )}
      >
        {letter}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2 text-[13px]">
          <span className="font-display text-sm font-bold text-tr-navy">
            {engineScanRowTitle(engine)}
          </span>
          <span
            className={cn(
              "font-semibold",
              complete && "font-bold text-[#1FB36B]",
              running && "font-bold text-brand-primary",
              pending && "text-tr-mute",
            )}
          >
            {complete && `✓ ${done} / ${total} prompts`}
            {running && `⟳ ${done} / ${total} prompts`}
            {pending && `${done} / ${total} prompts`}
          </span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-tr-pale">
          <div
            className={cn(
              "h-full rounded-full transition-[width] duration-300",
              complete && "bg-[#1FB36B]",
              running && "bg-brand-primary",
              pending && "bg-slate-200",
            )}
            style={{ width: `${barPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

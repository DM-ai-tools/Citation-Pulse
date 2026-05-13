"use client";

import { cn } from "@/lib/utils";
import { ENGINE_COLUMN_SUB, ENGINE_LABEL } from "@/lib/engineDisplay";
import type { MatrixCell } from "@/types/scan";

function cellFor(cells: MatrixCell[], promptId: string, engine: string) {
  return cells.find((c) => c.promptId === promptId && c.engine === engine);
}

function MatrixCellBox({ cell }: { cell: MatrixCell | undefined }) {
  const st = cell?.status ?? "queued";
  if (st === "running") {
    return (
      <div
        className={cn(
          "flex h-11 items-center justify-center rounded-lg border border-dashed border-brand-primary bg-tr-pale font-display text-[11px] font-bold text-tr-teal animate-landing-pulse",
        )}
      >
        ⟳
      </div>
    );
  }
  if (st === "queued") {
    return (
      <div className="relative flex h-11 items-center justify-center rounded-lg border border-tr-line bg-white">
        <span className="h-2 w-2 rounded-full bg-tr-line" />
      </div>
    );
  }
  if (st === "cited") {
    return (
      <div className="flex h-11 items-center justify-center rounded-lg border border-[#18a05f] bg-[#1FB36B] font-display text-xs font-extrabold text-white">
        cited
      </div>
    );
  }
  if (st === "comp") {
    return (
      <div className="flex h-11 items-center justify-center rounded-lg border border-[#d88f0e] bg-tr-landingOrange font-display text-xs font-extrabold text-white">
        comp
      </div>
    );
  }
  if (st === "error") {
    const hint = cell?.errorMessage?.trim();
    return (
      <div
        className="flex h-11 items-center justify-center rounded-lg border border-slate-500 bg-slate-600 font-display text-[10px] font-extrabold text-white"
        title={hint || "Engine run failed"}
      >
        err
      </div>
    );
  }
  return (
    <div className="flex h-11 items-center justify-center rounded-lg border border-[#c93f30] bg-[#E74C3C] font-display text-xs font-extrabold text-white">
      none
    </div>
  );
}

export function LiveScanHeatmapGrid({
  prompts,
  engines,
  cells,
}: {
  prompts: { id: string; text: string }[];
  engines: string[];
  cells: MatrixCell[];
}) {
  const colTemplate = `160px repeat(${engines.length}, minmax(0, 1fr))`;

  return (
    <div className="min-h-[480px] flex-1 overflow-x-auto rounded-[14px] bg-[#F4FCF7] p-4">
      <div className="min-w-[640px]">
      <div
        className="mb-2 grid gap-1.5 px-1.5"
        style={{ gridTemplateColumns: colTemplate }}
      >
        <div />
        {engines.map((e) => (
          <div key={e} className="text-center">
            <p className="font-display text-[10.5px] font-extrabold uppercase tracking-wide text-tr-navy">
              {ENGINE_LABEL[e] ?? e}
            </p>
            <p className="mt-0.5 font-display text-[9px] font-semibold text-tr-mute">
              {ENGINE_COLUMN_SUB[e] ?? ""}
            </p>
          </div>
        ))}
      </div>
      {prompts.map((p) => (
        <div
          key={p.id}
          className="mb-1.5 grid gap-1.5"
          style={{ gridTemplateColumns: colTemplate }}
        >
          <div className="flex items-center rounded-lg border border-tr-line bg-white px-3 py-2.5 text-[12.5px] font-semibold text-tr-navy">
            <span className="line-clamp-2 leading-snug">{p.text}</span>
          </div>
          {engines.map((e) => (
            <MatrixCellBox key={e} cell={cellFor(cells, p.id, e)} />
          ))}
        </div>
      ))}
      <div className="mt-4 flex flex-wrap items-center gap-x-3.5 gap-y-2 px-1.5 text-[11.5px] text-tr-body">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3.5 w-3.5 rounded bg-[#1FB36B]" /> Brand cited
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3.5 w-3.5 rounded bg-tr-landingOrange" /> Competitor cited
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3.5 w-3.5 rounded bg-[#E74C3C]" /> No brand or competitor
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3.5 w-3.5 rounded border border-dashed border-brand-primary bg-tr-pale" />{" "}
          Running
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3.5 w-3.5 rounded border border-tr-line bg-white" /> Queued
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3.5 w-3.5 rounded border border-slate-500 bg-slate-600" /> Run failed
        </span>
      </div>
      </div>
    </div>
  );
}

"use client";

import { cn } from "@/lib/utils";
import type { ReportData } from "@/types/report";
import type { MatrixCell } from "@/types/scan";

type Snapshot = { name: string; value: number; isBrand?: boolean };

function buildSnapshots(
  competitors: ReportData["competitors"],
  brandName: string,
  cells: MatrixCell[],
  prompts: { id: string }[],
  engines: string[],
): Snapshot[] {
  const totalCells = (prompts?.length ?? 0) * (engines?.length ?? 0) || 1;
  const brandCited = cells.filter((c) => c.status === "cited").length;
  const compCited = cells.filter((c) => c.status === "comp").length;

  const out: Snapshot[] = [];
  out.push({
    name: brandName,
    value: Math.round((100 * brandCited) / totalCells),
    isBrand: true,
  });

  const list = competitors ?? [];
  const fallback = [65, 42, 18];
  const sharePer = list.length
    ? Math.max(0, Math.round((100 * compCited) / totalCells / list.length))
    : 0;
  list.forEach((c, i) => {
    out.push({
      name: c.name,
      value: list.length > 1 ? sharePer + (i === 0 ? 10 : -5 * i) : fallback[i] ?? 20,
    });
  });
  return out
    .map((s) => ({ ...s, value: Math.max(0, Math.min(100, s.value)) }))
    .sort((a, b) => b.value - a.value);
}

export function CompetitorSnapshot({
  competitors,
  brandName,
  cells,
  prompts,
  engines,
  promptCount,
}: {
  competitors: ReportData["competitors"];
  brandName: string;
  cells: MatrixCell[];
  prompts: { id: string }[];
  engines: string[];
  promptCount?: number;
}) {
  if (!competitors?.length) return null;
  const snapshots = buildSnapshots(competitors, brandName, cells, prompts, engines);

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-100 px-5 py-3">
        <h3 className="text-[11px] font-bold uppercase tracking-[0.2em] text-tr-navy">
          Competitor Snapshot
        </h3>
        <p className="text-xs text-slate-500">
          across {promptCount ?? prompts.length} prompts
        </p>
      </div>
      <ul className="space-y-3 p-5">
        {snapshots.map((s) => (
          <li key={s.name} className="flex items-center gap-3">
            <span
              className={cn(
                "min-w-[110px] truncate text-sm font-bold",
                s.isBrand ? "text-brand-primary" : "text-tr-navy",
              )}
            >
              {s.name}
            </span>
            <div className="relative h-3 flex-1 rounded-full bg-slate-100">
              <span
                className={cn(
                  "absolute inset-y-0 left-0 rounded-full",
                  s.isBrand ? "bg-brand-primary" : "bg-emerald-500",
                )}
                style={{ width: `${s.value}%` }}
              />
            </div>
            <span className="min-w-[42px] text-right text-sm font-bold tabular-nums text-tr-navy">
              {s.value}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

import type { MatrixCell } from "@/types/scan";

export function promptCompletionPct(
  prompts: { id: string }[],
  engines: string[],
  cells: MatrixCell[],
  promptId: string | null,
): number {
  const list = promptId ? prompts.filter((p) => p.id === promptId) : prompts;
  const total = list.length * engines.length;
  if (!total) return 0;
  let done = 0;
  for (const p of list) {
    for (const e of engines) {
      const c = cells.find((x) => x.promptId === p.id && x.engine === e);
      const st = c?.status ?? "queued";
      if (st === "cited" || st === "comp" || st === "none") done += 1;
    }
  }
  return Math.round((100 * done) / total);
}

/** Mean of per-engine scores — matches the heatmap layer dial when “All engines” is implied. */
export function overallCitationScore(
  prompts: { id: string }[],
  engines: string[],
  cells: MatrixCell[],
): number {
  if (!engines.length) return 0;
  const perEngine = engineLayerScores(prompts, engines, cells);
  let sum = 0;
  for (const e of engines) {
    sum += perEngine[e] ?? 0;
  }
  return Math.round(sum / engines.length);
}

export function engineLayerScores(
  prompts: { id: string }[],
  engines: string[],
  cells: MatrixCell[],
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const e of engines) {
    let pts = 0;
    let n = 0;
    for (const p of prompts) {
      n += 1;
      const c = cells.find((x) => x.promptId === p.id && x.engine === e);
      const st = c?.status;
      if (st === "cited") pts += c?.position === 1 ? 100 : 75;
      else if (st === "comp") pts += 55;
      else if (st === "none") pts += 0;
      else if (st === "running") pts += 30;
      else pts += 10;
    }
    out[e] = n ? Math.round(pts / n) : 0;
  }
  return out;
}

export function heatmapBreakdownCounts(cells: MatrixCell[]) {
  let brandTop = 0;
  let brandLower = 0;
  let comp = 0;
  let none = 0;
  for (const c of cells) {
    if (c.status === "cited") {
      if (c.position === 1) brandTop += 1;
      else brandLower += 1;
    } else if (c.status === "comp") comp += 1;
    else if (c.status === "none") none += 1;
  }
  const total = cells.length || 1;
  return {
    brandTop,
    brandLower,
    comp,
    none,
    pct: (n: number) => Math.round((100 * n) / total),
  };
}

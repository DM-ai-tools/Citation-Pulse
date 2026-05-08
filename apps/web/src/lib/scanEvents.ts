import type { ScanEvent, ScanSnapshot } from "@/types/scan";

/** Pure reducer for SSE events → scan snapshot (TanStack Query cache updater). */
export function applyScanEvent(prev: ScanSnapshot | undefined, event: ScanEvent): ScanSnapshot {
  if (!prev) {
    throw new Error("applyScanEvent requires existing snapshot");
  }
  if (event.type === "scan.eta") {
    return { ...prev, status: prev.status === "completed" ? prev.status : "running" };
  }
  if (event.type === "scan.completed") {
    return {
      ...prev,
      status: "completed",
      score_overall: event.score,
    };
  }
  if (event.type === "engine.progress") {
    const per_engine = { ...prev.progress.per_engine };
    per_engine[event.engine] = { done: event.done, total: event.total };
    return { ...prev, progress: { per_engine } };
  }
  if (event.type === "cell.update") {
    const cells = [...prev.matrix.cells];
    const idx = cells.findIndex((c) => c.promptId === event.promptId && c.engine === event.engine);
    const next: typeof cells[0] = {
      promptId: event.promptId,
      engine: event.engine,
      status: event.status,
    };
    if (event.position !== undefined) next.position = event.position;
    if (idx >= 0) cells[idx] = next;
    else cells.push(next);
    return {
      ...prev,
      matrix: { cells },
    };
  }
  return prev;
}

export function parseScanEvent(data: string): ScanEvent | null {
  try {
    const o = JSON.parse(data) as ScanEvent;
    if (o && typeof o === "object" && "type" in o) return o;
  } catch {
    /* ignore */
  }
  return null;
}

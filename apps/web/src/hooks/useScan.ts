"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { applyScanEvent, parseScanEvent } from "@/lib/scanEvents";
import { getScan, scanStreamUrl } from "@/services/scans";
import type { ScanSnapshot } from "@/types/scan";
import { useEventSource } from "./useEventSource";

export function useScan(scanId: string) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["scan", scanId],
    queryFn: () => getScan(scanId),
    enabled: !!scanId,
    // Fallback when EventSource is blocked (CORS / mixed content / corporate proxy).
    refetchInterval: (query) => {
      const d = query.state.data;
      if (!d || d.status === "completed" || d.status === "failed") return false;
      // Poll faster near completion so status catches up if SSE missed scan.completed.
      const cells = d.matrix?.cells ?? [];
      const total = d.prompts.length * d.engines.length;
      let done = 0;
      for (const p of d.prompts) {
        for (const e of d.engines) {
          const c = cells.find((x) => x.promptId === p.id && x.engine === e);
          const st = c?.status ?? "queued";
          if (st === "cited" || st === "comp" || st === "none" || st === "error") done += 1;
        }
      }
      if (total > 0 && done >= total) return 2000;
      return 5000;
    },
    staleTime: 2000,
  });

  const done = q.data?.status === "completed" || q.data?.status === "failed";
  useEventSource(
    scanId ? scanStreamUrl(scanId) : null,
    (ev) => {
      let parsed: ReturnType<typeof parseScanEvent> = null;
      try {
        const o = JSON.parse(ev.data) as { type?: string };
        if (o?.type === "competitor.discovery.ready" || o?.type === "competitor.discovery.started") {
          void qc.invalidateQueries({ queryKey: ["scan", scanId] });
          return;
        }
        parsed = parseScanEvent(ev.data);
      } catch {
        return;
      }
      if (!parsed) return;
      qc.setQueryData(["scan", scanId], (prev) => {
        if (!prev) return prev;
        try {
          return applyScanEvent(prev as ScanSnapshot, parsed);
        } catch {
          return prev;
        }
      });
    },
    !!scanId && !done,
  );

  return q;
}

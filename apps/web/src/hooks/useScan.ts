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
      if (!d || d.status === "completed") return false;
      return 2500;
    },
  });

  const done = q.data?.status === "completed";
  useEventSource(
    scanId ? scanStreamUrl(scanId) : null,
    (ev) => {
      const parsed = parseScanEvent(ev.data);
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

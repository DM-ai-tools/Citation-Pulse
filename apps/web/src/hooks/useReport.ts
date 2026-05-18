"use client";

import { useQuery } from "@tanstack/react-query";
import { getScanReport } from "@/services/scans";

export function useReport(scanId: string) {
  return useQuery({
    queryKey: ["report", scanId],
    queryFn: () => getScanReport(scanId),
    enabled: !!scanId,
    // After API deploy (new SoV embed / scan SoV routes), tab focus picks up fresh JSON without a full cache clear.
    refetchOnWindowFocus: true,
    staleTime: 0,
    // Background competitor discovery finishes after the scan — poll until ready or skipped.
    refetchInterval: (query) => {
      const d = query.state.data;
      if (!d) return false;
      if (d.competitor_discovery_pending) return 3000;
      if (d.status !== "completed") return false;
      if (
        d.competitor_discovery &&
        !d.competitor_citation_visibility?.ranked_competitors?.length
      ) {
        return 3000;
      }
      if (!d.competitor_discovery && d.completed_at) {
        const ageMs = Date.now() - Date.parse(d.completed_at);
        if (ageMs >= 0 && ageMs < 120_000) return 3000;
      }
      return false;
    },
  });
}

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
  });
}

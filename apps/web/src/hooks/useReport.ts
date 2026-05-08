"use client";

import { useQuery } from "@tanstack/react-query";
import { getScanReport } from "@/services/scans";

export function useReport(scanId: string) {
  return useQuery({
    queryKey: ["report", scanId],
    queryFn: () => getScanReport(scanId),
    enabled: !!scanId,
  });
}

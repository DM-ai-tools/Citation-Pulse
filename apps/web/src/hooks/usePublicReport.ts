"use client";

import { useQuery } from "@tanstack/react-query";
import { getPublicReport } from "@/services/report";

export function usePublicReport(token: string) {
  return useQuery({
    queryKey: ["publicReport", token],
    queryFn: () => getPublicReport(token),
    enabled: !!token,
  });
}

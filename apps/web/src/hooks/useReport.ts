"use client";

import { useQuery } from "@tanstack/react-query";
import { getScanCompetitorCitations, getScanReport } from "@/services/scans";
import type { ReportData } from "@/types/report";

function visibilityHasCompetitors(vis: ReportData["competitor_citation_visibility"]): boolean {
  if (!vis) return false;
  const pools = [
    vis.ranked_competitors,
    vis.competitors,
    vis.all_ranked_competitors,
    ...(vis.by_prompt?.map((p) => p.ranked_competitors ?? p.competitors ?? p.all_ranked_competitors) ?? []),
  ];
  return pools.some((rows) => (rows?.length ?? 0) > 0);
}

function mergeReportData(
  lite: ReportData,
  full: ReportData,
  citations?: ReportData["competitor_citation_visibility"] | null,
): ReportData {
  const vis =
    citations ?? full.competitor_citation_visibility ?? lite.competitor_citation_visibility ?? null;
  return {
    ...lite,
    ...full,
    matrix: full.matrix?.cells?.length ? full.matrix : lite.matrix,
    competitor_discovery: full.competitor_discovery ?? lite.competitor_discovery,
    competitor_discovery_pending:
      full.competitor_discovery_pending ?? lite.competitor_discovery_pending,
    competitor_discovery_status:
      full.competitor_discovery_status ?? lite.competitor_discovery_status,
    competitor_citation_visibility: vis,
    user_provided_competitors:
      full.user_provided_competitors?.length
        ? full.user_provided_competitors
        : lite.user_provided_competitors,
    analysis_competitors:
      full.analysis_competitors?.length ? full.analysis_competitors : lite.analysis_competitors,
    opportunities: full.opportunities?.length ? full.opportunities : lite.opportunities,
  };
}

function litePollIntervalMs(data: ReportData | undefined): number | false {
  if (!data) return 3000;
  if (data.status !== "completed") return 3000;
  if (data.competitor_discovery_pending) return 4000;
  if (!data.competitor_discovery && data.competitor_discovery_status === "pending") return 4000;
  return false;
}

/**
 * Two-phase report load: fast lite payload (polls until discovery/citations ready), then full report.
 */
export function useReport(scanId: string) {
  const lite = useQuery({
    queryKey: ["report", scanId, "lite"],
    queryFn: () => getScanReport(scanId, { lite: true }),
    enabled: Boolean(scanId),
    staleTime: 5_000,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => litePollIntervalMs(query.state.data),
  });

  const full = useQuery({
    queryKey: ["report", scanId, "full"],
    queryFn: () => getScanReport(scanId),
    enabled: Boolean(scanId) && lite.isSuccess && lite.data?.status === "completed",
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });

  const competitorCitations = useQuery({
    queryKey: ["report", scanId, "competitor-citations"],
    queryFn: () => getScanCompetitorCitations(scanId),
    enabled:
      Boolean(scanId) && lite.data?.status === "completed" && (lite.isSuccess || full.isSuccess),
    staleTime: 10_000,
    retry: 2,
    refetchInterval: (query) => {
      if (visibilityHasCompetitors(query.state.data?.competitor_citation_visibility)) {
        return false;
      }
      if ((query.state.fetchFailureCount ?? 0) >= 5) return false;
      const ageMs = lite.data?.completed_at ? Date.now() - Date.parse(lite.data.completed_at) : 0;
      if (ageMs > 90_000) return false;
      return 3000;
    },
  });

  // Include full report visibility — the full report always builds competitor_citation_visibility
  // but the previous code discarded it in favour of the dedicated citations query only.
  const citationVis =
    competitorCitations.data?.competitor_citation_visibility ??
    full.data?.competitor_citation_visibility ??
    lite.data?.competitor_citation_visibility ??
    null;

  const citationsQuerySettled =
    competitorCitations.isSuccess || competitorCitations.isError || !competitorCitations.isEnabled;

  // Spinner only while scan is done but citation visibility has not arrived from any source yet.
  const isCitationsLoading =
    lite.data?.status === "completed" &&
    !citationVis &&
    !citationsQuerySettled &&
    competitorCitations.isFetching;

  const citationsFetchError = competitorCitations.isError && !citationVis;

  const data =
    lite.data && full.data
      ? mergeReportData(lite.data, full.data, citationVis)
      : lite.data
        ? mergeReportData(lite.data, lite.data, citationVis)
        : full.data;

  const isLoading = lite.isLoading;
  const isEnriching =
    lite.isSuccess &&
    full.isEnabled &&
    full.isFetching &&
    !full.isError &&
    !full.data?.sov_multi_engine;

  return {
    data,
    isLoading,
    isError: lite.isError && !lite.data,
    error: lite.error ?? full.error ?? competitorCitations.error,
    isEnriching,
    isSuccess: Boolean(data),
    isCitationsLoading,
    citationsFetchError,
    dataUpdatedAt:
      competitorCitations.dataUpdatedAt || full.dataUpdatedAt || lite.dataUpdatedAt,
    refetch: async () => {
      await Promise.all([lite.refetch(), full.refetch(), competitorCitations.refetch()]);
    },
  };
}

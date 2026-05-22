"use client";

import { useEffect, useMemo, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { getScanReport } from "@/services/scans";
import { rememberDashboardScan } from "@/lib/dashboardScanPreference";
import { LiveCitationMatrix } from "@/components/scan/LiveCitationMatrix";
import { LiveScanCompetitors } from "@/components/scan/LiveScanCompetitors";
import { ScanLiveHeader } from "@/components/scan/ScanLiveHeader";
import { ScanProgressColumn } from "@/components/scan/ScanProgressColumn";
import { ScanStallNotice } from "@/components/scan/ScanStallNotice";
import { ErrorState, Skeleton } from "@/components/primitives";
import { useScan } from "@/hooks/useScan";
import { publicApiBaseUrl } from "@/services/apiClient";
import {
  matrixAllEnginesTerminal,
  scanMatrixFullyComplete,
  scanReadyForReport,
} from "@/lib/matrixStats";

export default function LiveScanPage() {
  const params = useParams<{ scanId: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const scanId = params.scanId;
  const q = useScan(scanId);

  const matrixReady = useMemo(() => {
    const d = q.data;
    if (!d) return false;
    return matrixAllEnginesTerminal(d.prompts, d.engines, d.matrix.cells, d.status);
  }, [q.data]);

  const readyForReport = useMemo(() => {
    const d = q.data;
    if (!d) return false;
    return scanReadyForReport(d.status, d.prompts, d.engines, d.matrix.cells);
  }, [q.data]);

  const prevCompletedRef = useRef(false);
  const redirectedRef = useRef(false);

  useEffect(() => {
    prevCompletedRef.current = false;
    redirectedRef.current = false;
  }, [scanId]);

  useEffect(() => {
    if (scanId) rememberDashboardScan(scanId);
  }, [scanId]);

  /* Matrix finished but status still "running" (missed scan.completed SSE) — sync from API. */
  useEffect(() => {
    const d = q.data;
    if (!d || d.status === "completed" || d.status === "failed") return;
    if (!scanMatrixFullyComplete(d.prompts, d.engines, d.matrix.cells)) return;
    void q.refetch();
  }, [q.data?.status, q.data?.matrix.cells, q]);

  /* After the API marks the scan completed, pull a fresh snapshot once so the matrix
     matches the server if SSE events arrived out of order. */
  useEffect(() => {
    const terminal = q.data?.status === "completed" || q.data?.status === "failed";
    if (terminal && !prevCompletedRef.current) {
      prevCompletedRef.current = true;
      void q.refetch();
    }
    if (!terminal) prevCompletedRef.current = false;
  }, [q.data?.status, q]);

  /* Navigate to report when the scan is done (status terminal OR all matrix cells finished). */
  useEffect(() => {
    if (!scanId || !q.data || redirectedRef.current) return;
    if (!readyForReport) return;

    void queryClient.prefetchQuery({
      queryKey: ["report", scanId, "lite"],
      queryFn: () => getScanReport(scanId, { lite: true }),
    });

    const statusTerminal =
      q.data.status === "completed" || q.data.status === "failed";
    const delay = statusTerminal && matrixReady ? 800 : statusTerminal ? 2500 : 3500;

    const id = window.setTimeout(() => {
      redirectedRef.current = true;
      router.replace(`/report/${scanId}`);
    }, delay);
    return () => window.clearTimeout(id);
  }, [readyForReport, matrixReady, q.data, router, scanId, queryClient]);

  /* Hard cap: never leave the user on the scan page more than ~2 minutes. */
  useEffect(() => {
    if (!scanId || redirectedRef.current) return;
    const id = window.setTimeout(() => {
      if (redirectedRef.current) return;
      redirectedRef.current = true;
      router.replace(`/report/${scanId}`);
    }, 120_000);
    return () => window.clearTimeout(id);
  }, [scanId, router]);

  if (q.isLoading) {
    return (
      <div className="min-h-screen bg-[#F4FCF7]">
        <div className="mx-auto max-w-[1280px] px-6 py-10">
          <Skeleton className="h-[76px] w-full rounded-lg" />
          <div className="mt-8 grid gap-7 lg:grid-cols-[1.05fr_1fr]">
            <Skeleton className="min-h-[520px] rounded-[18px]" />
            <Skeleton className="min-h-[520px] rounded-[18px]" />
          </div>
        </div>
      </div>
    );
  }

  if (q.isError || !q.data) {
    return (
      <div className="min-h-screen bg-[#F4FCF7] py-10">
        <div className="mx-auto max-w-[1280px] px-6">
          <ErrorState
            message={
              q.error instanceof Error
                ? `${q.error.message} — API: ${publicApiBaseUrl()}. Start the backend with npm run dev:api (port 8000) or npm run dev:stack from the repo root, then refresh.`
                : `Scan could not be loaded. Start the API (npm run dev:api) then refresh. API: ${publicApiBaseUrl()}`
            }
            onRetry={() => q.refetch()}
          />
        </div>
      </div>
    );
  }

  const data = q.data;

  return (
    <div className="min-h-screen bg-[#F4FCF7]">
      <ScanLiveHeader status={data.status} url={data.submitted_url} />
      <div className="mx-auto max-w-[1280px] px-6">
        <ScanStallNotice data={data} />
      </div>
      <div className="mx-auto grid max-w-[1280px] gap-7 px-6 py-8 pb-16 lg:grid-cols-[1.05fr_1fr] lg:items-start">
        <div className="space-y-7">
          <ScanProgressColumn data={data} scanId={scanId} />
          <LiveScanCompetitors data={data} />
        </div>
        <LiveCitationMatrix data={data} />
      </div>
    </div>
  );
}

"use client";

import { useEffect, useMemo, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { rememberDashboardScan } from "@/lib/dashboardScanPreference";
import { LiveCitationMatrix } from "@/components/scan/LiveCitationMatrix";
import { ScanLiveHeader } from "@/components/scan/ScanLiveHeader";
import { ScanProgressColumn } from "@/components/scan/ScanProgressColumn";
import { ScanStallNotice } from "@/components/scan/ScanStallNotice";
import { ErrorState, Skeleton } from "@/components/primitives";
import { useScan } from "@/hooks/useScan";
import { publicApiBaseUrl } from "@/services/apiClient";
import { matrixAllEnginesTerminal } from "@/lib/matrixStats";

export default function LiveScanPage() {
  const params = useParams<{ scanId: string }>();
  const router = useRouter();
  const scanId = params.scanId;
  const q = useScan(scanId);

  const matrixReady = useMemo(() => {
    const d = q.data;
    if (!d) return false;
    return matrixAllEnginesTerminal(d.prompts, d.engines, d.matrix.cells, d.status);
  }, [q.data]);

  const prevCompletedRef = useRef(false);

  useEffect(() => {
    prevCompletedRef.current = false;
  }, [scanId]);

  useEffect(() => {
    if (scanId) rememberDashboardScan(scanId);
  }, [scanId]);

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

  useEffect(() => {
    const terminal = q.data?.status === "completed" || q.data?.status === "failed";
    if (terminal && matrixReady) {
      router.replace(`/report/${scanId}`);
    }
  }, [q.data?.status, matrixReady, router, scanId]);

  /* If SSE never updates the matrix but the scan is already completed, do not block the funnel forever. */
  useEffect(() => {
    const terminal = q.data?.status === "completed" || q.data?.status === "failed";
    if (!terminal || matrixReady) return;
    const id = window.setTimeout(() => {
      router.replace(`/report/${scanId}`);
    }, 45_000);
    return () => window.clearTimeout(id);
  }, [q.data?.status, matrixReady, router, scanId]);

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
        <ScanProgressColumn data={data} scanId={scanId} />
        <LiveCitationMatrix data={data} />
      </div>
    </div>
  );
}

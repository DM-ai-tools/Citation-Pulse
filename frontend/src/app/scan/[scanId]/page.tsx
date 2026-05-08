"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { rememberDashboardScan } from "@/lib/dashboardScanPreference";
import { LiveCitationMatrix } from "@/components/scan/LiveCitationMatrix";
import { ScanLiveHeader } from "@/components/scan/ScanLiveHeader";
import { ScanProgressColumn } from "@/components/scan/ScanProgressColumn";
import { ErrorState, Skeleton } from "@/components/primitives";
import { useScan } from "@/hooks/useScan";

export default function LiveScanPage() {
  const params = useParams<{ scanId: string }>();
  const router = useRouter();
  const scanId = params.scanId;
  const q = useScan(scanId);

  useEffect(() => {
    if (scanId) rememberDashboardScan(scanId);
  }, [scanId]);

  useEffect(() => {
    if (q.data?.status === "completed") {
      router.replace(`/report/${scanId}`);
    }
  }, [q.data?.status, router, scanId]);

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
          <ErrorState message="Scan could not be loaded." onRetry={() => q.refetch()} />
        </div>
      </div>
    );
  }

  const data = q.data;

  return (
    <div className="min-h-screen bg-[#F4FCF7]">
      <ScanLiveHeader status={data.status} url={data.submitted_url} />
      <div className="mx-auto grid max-w-[1280px] gap-7 px-6 py-8 pb-16 lg:grid-cols-[1.05fr_1fr] lg:items-start">
        <ScanProgressColumn data={data} scanId={scanId} />
        <LiveCitationMatrix data={data} />
      </div>
    </div>
  );
}

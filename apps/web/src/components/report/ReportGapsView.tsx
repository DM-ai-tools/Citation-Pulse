"use client";

import Link from "next/link";
import { GapsPanel } from "@/components/dashboard/GapsPanel";
import { ErrorState, Skeleton } from "@/components/primitives";
import { useReport } from "@/hooks/useReport";

/** Dashboard-style gaps list for a scan report (expand rows in place). */
export function ReportGapsView({
  scanId,
  reportTopBar,
}: {
  scanId: string;
  reportTopBar?: React.ReactNode;
}) {
  const q = useReport(scanId);

  if (q.isLoading) {
    return (
      <div className="min-h-screen bg-[#F4FCF7]">
        {reportTopBar}
        <div className="mx-auto max-w-4xl space-y-6 px-6 py-8">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-[420px] w-full rounded-[18px]" />
        </div>
      </div>
    );
  }

  if (q.isError || !q.data) {
    return (
      <div className="min-h-screen bg-[#F4FCF7] py-10">
        {reportTopBar}
        <div className="mx-auto max-w-4xl px-6">
          <ErrorState message="Gap details not available." onRetry={() => q.refetch()} />
        </div>
      </div>
    );
  }

  const d = q.data;
  const urlHost = d.submitted_url.replace(/^https?:\/\//, "").split("/")[0] ?? "";
  const brandLabel = d.brand?.name ?? urlHost;

  return (
    <div className="min-h-screen bg-[#F4FCF7]" data-testid="report-gaps-view">
      {reportTopBar}
      <main className="mx-auto max-w-4xl space-y-6 px-6 py-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Link
              href={`/report/${encodeURIComponent(scanId)}`}
              className="font-display text-[12.5px] font-bold text-brand-primary hover:underline"
            >
              ← Back to citation report
            </Link>
            <h1 className="mt-3 font-display text-2xl font-bold text-tr-navy">Gaps</h1>
            <p className="mt-2 text-sm text-tr-mute">
              Visibility gaps for <strong className="font-semibold text-tr-navy">{brandLabel}</strong> — expand any
              row for a prompt-specific breakdown.
            </p>
          </div>
        </div>

        <GapsPanel scanReport={d} />
      </main>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useState } from "react";
import { ErrorState, Skeleton } from "@/components/primitives";
import { GapsPanel } from "@/components/dashboard/GapsPanel";
import { useDashboardWorkspace } from "@/lib/useDashboardWorkspace";

export default function DashboardGapsPage() {
  const { brandId, brandName, isLoading, isError, refetch, useScanReport, report } =
    useDashboardWorkspace();
  const [summaryView, setSummaryView] = useState(false);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-[420px] w-full rounded-[18px]" />
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState
        message="Could not load workspace. Run a scan from the home page or check your API connection."
        onRetry={refetch}
      />
    );
  }

  if (!useScanReport && !brandId) {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-700">
        <p className="font-semibold text-ink-900">No scan data yet</p>
        <p className="mt-2 text-slate-600">Run a free scan from the landing page, then return here.</p>
        <Link href="/landing" className="mt-4 inline-block text-sm font-semibold text-brand-primary hover:underline">
          Run a scan →
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-900">Gaps</h1>
          <p className="mt-2 text-sm text-slate-600">
            Visibility gaps for <strong className="font-semibold text-ink-900">{brandName}</strong>
            {summaryView ? " — summary view (title and description only)." : " — expand any row for full analysis."}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSummaryView(true)}
            className={
              summaryView
                ? "rounded-lg bg-ink-900 px-4 py-2 text-sm font-semibold text-white"
                : "rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-ink-800 hover:bg-slate-50"
            }
          >
            Gaps & descriptions
          </button>
          <button
            type="button"
            onClick={() => setSummaryView(false)}
            className={
              !summaryView
                ? "rounded-lg bg-ink-900 px-4 py-2 text-sm font-semibold text-white"
                : "rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-ink-800 hover:bg-slate-50"
            }
          >
            Full analysis
          </button>
        </div>
      </div>

      <GapsPanel
        brandId={useScanReport ? undefined : brandId}
        scanReport={useScanReport ? report : undefined}
        summaryOnly={summaryView}
      />
    </div>
  );
}

"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { ReportGapsView } from "@/components/report/ReportGapsView";
import { ReportTopBar } from "@/components/report/ReportTopBar";
import { useReport } from "@/hooks/useReport";
import { shareScan } from "@/services/scans";
import { toast } from "sonner";

function formatReportTimestamp(iso: string | null | undefined, fallbackMs: number) {
  const raw = iso ? Date.parse(iso) : fallbackMs;
  const d = Number.isFinite(raw) ? new Date(raw) : new Date(fallbackMs);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function ReportGapsPage() {
  const params = useParams<{ scanId?: string | string[] }>();
  const rawScanId = params?.scanId;
  const scanId =
    typeof rawScanId === "string" ? rawScanId : Array.isArray(rawScanId) ? (rawScanId[0] ?? "") : "";
  const q = useReport(scanId);

  const generatedAt = useMemo(() => {
    if (!q.data) return "";
    return formatReportTimestamp(q.data.completed_at, q.dataUpdatedAt);
  }, [q.data, q.dataUpdatedAt]);

  const urlHost = q.data?.submitted_url.replace(/^https?:\/\//, "").split("/")[0] ?? "";

  async function onShare() {
    try {
      const origin = typeof window !== "undefined" ? window.location.origin : "";
      const r = await shareScan(scanId, true);
      const url = r.share_token ? `${origin}/r/${r.share_token}` : "";
      if (url) await navigator.clipboard.writeText(url);
      toast.success(url ? "Share link copied" : "Sharing enabled");
      q.refetch();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Share failed");
    }
  }

  const topBar =
    scanId && urlHost ? (
      <ReportTopBar urlHost={urlHost} generatedAt={generatedAt} onShare={onShare} onPdf={() => window.print()} />
    ) : null;

  return <ReportGapsView scanId={scanId} reportTopBar={topBar} />;
}

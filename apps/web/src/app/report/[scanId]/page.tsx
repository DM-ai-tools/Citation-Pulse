"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { CitationHeatmap } from "@/components/report/CitationHeatmap";
import { CitationsList } from "@/components/report/CitationsList";
import { DfyCta } from "@/components/report/DfyCta";
import { EngineLayerSelector } from "@/components/report/EngineLayerSelector";
import { HeatmapBreakdownCards } from "@/components/report/HeatmapBreakdownCards";
import { PromptEngineScoreMatrix } from "@/components/report/PromptEngineScoreMatrix";
import { ReportHero } from "@/components/report/ReportHero";
import { ReportTopBar } from "@/components/report/ReportTopBar";
import { TopGapOpportunities } from "@/components/report/TopGapOpportunities";
import { ErrorState, Skeleton } from "@/components/primitives";
import { useReport } from "@/hooks/useReport";
import { rememberDashboardScan } from "@/lib/dashboardScanPreference";
import { engineLayerScores, overallCitationScore } from "@/lib/matrixStats";
import { engineTitle } from "@/lib/engineDisplay";
import { shareScan } from "@/services/scans";
import type { MatrixCell } from "@/types/scan";

function formatReportTimestamp(iso: string | null | undefined, fallbackMs: number) {
  const raw = iso ? Date.parse(iso) : fallbackMs;
  const d = Number.isFinite(raw) ? new Date(raw) : new Date(fallbackMs);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function ReportPage() {
  const params = useParams<{ scanId: string }>();
  const scanId = params.scanId;
  const q = useReport(scanId);
  const [layer, setLayer] = useState<string | null>(null);

  useEffect(() => {
    if (scanId && q.data?.submitted_url) {
      rememberDashboardScan(scanId, q.data.submitted_url);
    }
  }, [scanId, q.data?.submitted_url]);

  const engines = q.data?.engines ?? [];
  const allCells = useMemo(() => q.data?.matrix.cells ?? [], [q.data?.matrix.cells]);

  const breakdownCells: MatrixCell[] = useMemo(() => {
    if (!layer) return allCells;
    return allCells.filter((c) => c.engine === layer);
  }, [allCells, layer]);

  const scores = useMemo(() => {
    if (!q.data) return {} as Record<string, number>;
    return engineLayerScores(q.data.prompts, q.data.engines, allCells);
  }, [q.data, allCells]);

  const overallScore = useMemo(() => {
    if (!q.data) return 0;
    return overallCitationScore(q.data.prompts, q.data.engines, allCells);
  }, [q.data, allCells]);

  const generatedAt = useMemo(() => {
    if (!q.data) return "";
    return formatReportTimestamp(q.data.completed_at, q.dataUpdatedAt);
  }, [q.data, q.dataUpdatedAt]);

  if (q.isLoading) {
    return (
      <div className="min-h-screen bg-[#F4FCF7]">
        <Skeleton className="h-[76px] w-full" />
        <div className="mx-auto max-w-[1280px] px-6 py-10">
          <Skeleton className="h-56 w-full rounded-b-[22px]" />
          <Skeleton className="mt-8 h-24 w-full rounded-[14px]" />
          <Skeleton className="mt-8 h-96 w-full rounded-[18px]" />
        </div>
      </div>
    );
  }

  if (q.isError || !q.data) {
    return (
      <div className="min-h-screen bg-[#F4FCF7] py-10">
        <div className="mx-auto max-w-[1280px] px-6">
          <ErrorState message="Report not available yet." onRetry={() => q.refetch()} />
        </div>
      </div>
    );
  }

  const d = q.data;
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const urlHost = d.submitted_url.replace(/^https?:\/\//, "").split("/")[0] ?? "";
  const brandName = d.brand?.name ?? urlHost;
  const layerScore = layer ? (scores[layer] ?? 0) : overallScore;

  async function onShare() {
    try {
      const r = await shareScan(scanId, true);
      const url = r.share_token ? `${origin}/r/${r.share_token}` : "";
      if (url) await navigator.clipboard.writeText(url);
      toast.success(url ? "Share link copied" : "Sharing enabled");
      q.refetch();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Share failed");
    }
  }

  return (
    <div className="min-h-screen bg-[#F4FCF7]">
      <ReportTopBar
        urlHost={urlHost}
        generatedAt={generatedAt}
        onShare={onShare}
        onPdf={() => window.print()}
      />

      <div className="mx-auto max-w-[1280px] px-6">
        <ReportHero
          brandName={brandName}
          urlHost={urlHost}
          locale={d.locale}
          promptCount={d.prompts.length}
          engineCount={d.engines.length}
          competitorCount={d.competitors?.length ?? 0}
          score={overallScore}
        />
      </div>

      <div className="mx-auto max-w-[1280px] px-6 pt-7">
        <EngineLayerSelector engines={engines} value={layer} onChange={setLayer} scores={scores} />
      </div>

      <div className="mx-auto grid max-w-[1280px] gap-6 px-6 py-6 pb-8 lg:grid-cols-[1.4fr_1fr] lg:items-start">
        <div className="flex flex-col gap-5">
          <CitationHeatmap
            prompts={d.prompts}
            engines={engines}
            cells={allCells}
            mode="final"
            visual="tiles"
            layout="report"
            title="Citation Heatmap"
            layerLabel={layer ? engineTitle(layer) : null}
          />
          <HeatmapBreakdownCards
            cells={breakdownCells}
            layer={layer}
            promptCount={d.prompts.length}
            engineCount={d.engines.length}
            citationScore={layerScore}
          />
          <CitationsList
            cells={allCells}
            engineFilter={layer}
            title={layer ? `Citations from ${engineTitle(layer)}` : "Citations Found"}
          />
        </div>
        <div className="flex flex-col gap-5">
          <PromptEngineScoreMatrix prompts={d.prompts} engines={d.engines} cells={d.matrix.cells} />
          <DfyCta />
        </div>
      </div>

      <div className="mx-auto max-w-[1280px] px-6 pb-10">
        <TopGapOpportunities opportunities={d.opportunities ?? []} />
      </div>

      <p className="pb-10 text-center text-[13px] text-tr-mute">
        <Link href="/" className="font-semibold text-brand-primary hover:underline">
          ← Landing
        </Link>
        <span className="mx-2">·</span>
        <Link href={`/scan/${scanId}`} className="font-semibold text-brand-primary hover:underline">
          Previous: Live scan
        </Link>
        <span className="mx-2">·</span>
        {d.share_token ? (
          <Link href={`/r/${d.share_token}`} className="font-semibold text-brand-primary hover:underline">
            Next: Shared Report →
          </Link>
        ) : (
          <span>Next: Shared Report →</span>
        )}
      </p>
    </div>
  );
}

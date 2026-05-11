"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { BrandIdentityCard } from "@/components/report/BrandIdentityCard";
import { CitationHeatmap } from "@/components/report/CitationHeatmap";
import { CompetitorSnapshot } from "@/components/report/CompetitorSnapshot";
import { EngineLayerSelector } from "@/components/report/EngineLayerSelector";
import { HeatmapBreakdownCards } from "@/components/report/HeatmapBreakdownCards";
import { PromptEngineScoreMatrix } from "@/components/report/PromptEngineScoreMatrix";
import { PublicCheckYourOwnCta } from "@/components/report/PublicCheckYourOwnCta";
import { PublicReportFooter } from "@/components/report/PublicReportFooter";
import { TopGapOpportunities } from "@/components/report/TopGapOpportunities";
import { PublicReportTopBar } from "@/components/report/PublicReportTopBar";
import { ReportHero } from "@/components/report/ReportHero";
import { Container } from "@/components/layout/Container";
import { ErrorState, Skeleton } from "@/components/primitives";
import { ShareBanner } from "@/components/shared/ShareBanner";
import { usePublicReport } from "@/hooks/usePublicReport";
import { engineLayerScores, overallCitationScore } from "@/lib/matrixStats";
import { engineTitle } from "@/lib/engineDisplay";
import type { MatrixCell } from "@/types/scan";

export default function PublicReportPage() {
  const params = useParams<{ shareToken: string }>();
  const token = params.shareToken;
  const q = usePublicReport(token);
  const [layer, setLayer] = useState<string | null>(null);

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
    return new Date().toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }, []);

  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const shareUrl = `${origin}/r/${token}`;

  if (q.isLoading) {
    return (
      <div className="min-h-screen bg-tr-page">
        <Container className="space-y-6 py-8">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-56 w-full" />
          <Skeleton className="h-96 w-full" />
        </Container>
      </div>
    );
  }

  if (q.isError || !q.data) {
    return (
      <div className="min-h-screen bg-tr-page py-10">
        <Container>
          <ErrorState message="This shared report is unavailable." />
        </Container>
      </div>
    );
  }

  const d = q.data;
  const urlHost = d.submitted_url.replace(/^https?:\/\//, "").split("/")[0] ?? "";
  const brandName = d.brand?.name ?? urlHost;
  const layerScore = layer ? (scores[layer] ?? 0) : overallScore;

  return (
    <div className="flex min-h-screen flex-col bg-tr-page">
      <Container className="pt-4">
        <ShareBanner shareUrl={shareUrl} />
      </Container>
      <PublicReportTopBar onPdf={() => window.print()} />
      <Container className="flex-1 space-y-6 py-6 lg:space-y-8 lg:py-8">
        <BrandIdentityCard
          brandName={brandName}
          urlHost={urlHost}
          description={d.brand?.domains?.[0]}
        />

        <ReportHero
          brandName={brandName}
          urlHost={urlHost}
          locale={d.locale}
          promptCount={d.prompts.length}
          engineCount={d.engines.length}
          competitorCount={d.competitors?.length ?? 0}
          score={overallScore}
          variant="public"
          generatedAt={generatedAt}
        />

        <EngineLayerSelector engines={engines} value={layer} onChange={setLayer} scores={scores} />

        <div className="grid gap-6 lg:grid-cols-12 lg:items-start">
          <div className="space-y-6 lg:col-span-7">
            <CitationHeatmap
              prompts={d.prompts}
              engines={engines}
              cells={allCells}
              mode="final"
              visual="tiles"
              title="Citation heatmap"
              layerLabel={layer ? engineTitle(layer) : null}
            />
            <HeatmapBreakdownCards
              cells={breakdownCells}
              layer={layer}
              promptCount={d.prompts.length}
              engineCount={d.engines.length}
              citationScore={layerScore}
            />
            <TopGapOpportunities opportunities={d.opportunities ?? []} />
          </div>
          <div className="space-y-6 lg:col-span-5">
            <PromptEngineScoreMatrix
              prompts={d.prompts}
              engines={d.engines}
              cells={d.matrix.cells}
              title="Prompt × Engine Score"
            />
            <CompetitorSnapshot
              competitors={d.competitors || []}
              brandName={brandName}
              cells={allCells}
              prompts={d.prompts}
              engines={d.engines}
              promptCount={d.prompts.length}
            />
          </div>
        </div>

        <PublicCheckYourOwnCta />
      </Container>
      <PublicReportFooter />
    </div>
  );
}

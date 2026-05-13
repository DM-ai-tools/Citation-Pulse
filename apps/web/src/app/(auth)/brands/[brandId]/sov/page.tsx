"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { BrandSovDashboard } from "@/components/sov/BrandSovDashboard";
import { ErrorState, Skeleton } from "@/components/primitives";
import { apiFetch } from "@/lib/api";

type BrandRow = { id: string; name: string; domains?: string[] };

type SoVMultiEntityResponse = {
  primary_brand_id: string;
  range_days: number;
  engines: string[];
  entities: {
    entity_id: string;
    name: string;
    role: string;
    shares_by_engine: Record<string, number>;
  }[];
  totals?: {
    brand_citations: number;
    competitor_citations: number;
  };
};

type MultiWeeklyResponse = {
  primary_brand_id: string;
  weeks: number;
  entities: { entity_id: string; name: string; role: string }[];
  series: { week_start: string; shares: Record<string, number>; tracked_citations: number }[];
};

export default function BrandSovPage() {
  const params = useParams<{ brandId: string }>();
  const brandId = params.brandId;

  const brand = useQuery({
    queryKey: ["brand", brandId],
    queryFn: async (): Promise<BrandRow> => {
      const r = await apiFetch(`/api/v1/brands/${encodeURIComponent(brandId)}`);
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    enabled: !!brandId,
  });

  const multi = useQuery({
    queryKey: ["sov-multi-engine", brandId, "84d"],
    queryFn: async (): Promise<SoVMultiEntityResponse> => {
      const r = await apiFetch(`/api/v1/brands/${encodeURIComponent(brandId)}/sov/multi-engine?range=84d`);
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    enabled: !!brandId && brand.isSuccess,
  });

  const weekly = useQuery({
    queryKey: ["sov-multi-weekly", brandId],
    queryFn: async (): Promise<MultiWeeklyResponse> => {
      const r = await apiFetch(
        `/api/v1/brands/${encodeURIComponent(brandId)}/sov/multi-weekly-trend?weeks=12`,
      );
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    enabled: !!brandId && brand.isSuccess,
  });

  if (brand.isPending || multi.isPending || weekly.isPending) {
    return (
      <div className="mx-auto max-w-6xl space-y-6">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-[420px] w-full rounded-2xl" />
      </div>
    );
  }

  if (brand.isError || !brand.data) {
    return <ErrorState message="Could not load brand." onRetry={() => brand.refetch()} />;
  }

  if (multi.isError || !multi.data) {
    return <ErrorState message="Could not load SoV breakdown." onRetry={() => multi.refetch()} />;
  }

  if (weekly.isError || !weekly.data) {
    return <ErrorState message="Could not load weekly SoV trend." onRetry={() => weekly.refetch()} />;
  }

  return <BrandSovDashboard brandName={brand.data.name} multi={multi.data} weekly={weekly.data} />;
}

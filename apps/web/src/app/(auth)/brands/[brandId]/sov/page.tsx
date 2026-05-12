"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, ErrorState, Skeleton } from "@/components/primitives";
import { apiFetch } from "@/lib/api";
import { engineTitle } from "@/lib/engineDisplay";
import { cn } from "@/lib/utils";

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
};

type WeeklyTrendResponse = {
  primary_brand_id: string;
  focus_entity_id: string;
  weeks: number;
  series: { week_start: string; share: number }[];
};

export default function BrandSovPage() {
  const params = useParams<{ brandId: string }>();
  const brandId = params.brandId;
  const [focusEntityId, setFocusEntityId] = useState<string | null>(null);

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
    queryKey: ["sov-multi-engine", brandId],
    queryFn: async (): Promise<SoVMultiEntityResponse> => {
      const r = await apiFetch(`/api/v1/brands/${encodeURIComponent(brandId)}/sov/multi-engine?range=30d`);
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    enabled: !!brandId && brand.isSuccess,
  });

  const selectedEntity = focusEntityId ?? brandId;
  const trend = useQuery({
    queryKey: ["sov-entity-weekly", brandId, selectedEntity],
    queryFn: async (): Promise<WeeklyTrendResponse> => {
      const r = await apiFetch(
        `/api/v1/brands/${encodeURIComponent(brandId)}/sov/entity-weekly-trend?entity_id=${encodeURIComponent(selectedEntity)}&weeks=12`,
      );
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    enabled: !!brandId && !!selectedEntity && brand.isSuccess,
  });

  const barData = useMemo(() => {
    const ents = multi.data?.entities ?? [];
    const engList = multi.data?.engines ?? [];
    const row = ents.find((e) => e.entity_id === selectedEntity);
    if (!row || !engList.length) return [];
    return engList.map((eng) => ({
      engine: engineTitle(eng),
      share: row.shares_by_engine[eng] ?? 0,
      sharePct: Math.round((row.shares_by_engine[eng] ?? 0) * 100),
    }));
  }, [multi.data?.entities, multi.data?.engines, selectedEntity]);

  const lineData = useMemo(
    () =>
      (trend.data?.series ?? []).map((p) => ({
        week: p.week_start.slice(5),
        sharePct: Math.round(p.share * 100),
      })),
    [trend.data?.series],
  );

  if (brand.isPending || multi.isPending) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-72 rounded-xl" />
          <Skeleton className="h-72 rounded-xl" />
        </div>
      </div>
    );
  }

  if (brand.isError || !brand.data) {
    return <ErrorState message="Could not load brand." onRetry={() => brand.refetch()} />;
  }

  if (multi.isError || !multi.data) {
    return <ErrorState message="Could not load SoV breakdown." onRetry={() => multi.refetch()} />;
  }

  const entities = multi.data.entities;

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            <Link href="/dashboard" className="text-brand-primary hover:underline">
              Dashboard
            </Link>
            <span className="mx-2 text-slate-300">/</span>
            Share of voice
          </p>
          <h1 className="mt-1 font-display text-2xl font-bold text-ink-900">{brand.data.name}</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            Citation share on your monitored prompts: pick your brand or a linked competitor to see share by engine and
            weekly trend. Competitors are matched by domain lists on each brand record.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {entities.map((e) => (
          <button
            key={e.entity_id}
            type="button"
            onClick={() => setFocusEntityId(e.entity_id === brandId ? null : e.entity_id)}
            className={cn(
              "rounded-full border px-4 py-2 text-sm font-semibold transition-colors",
              (focusEntityId ?? brandId) === e.entity_id
                ? "border-ink-900 bg-ink-900 text-white"
                : "border-slate-200 bg-white text-ink-800 hover:border-slate-300",
            )}
          >
            {e.role === "brand" ? "My brand" : e.name}
          </button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-slate-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-ink-900">SoV trend (weekly)</h2>
          <p className="mt-1 text-xs text-slate-500">Share of citations matching this entity’s domains · last 12 weeks</p>
          <div className="mt-4 h-64">
            {trend.isPending ? (
              <Skeleton className="h-full w-full rounded-lg" />
            ) : trend.isError ? (
              <p className="text-sm text-rose-600">Trend failed to load.</p>
            ) : lineData.length === 0 ? (
              <p className="text-sm text-slate-500">No finished runs in this window yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={lineData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} width={40} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => [`${v}%`, "Share"]} />
                  <Line type="monotone" dataKey="sharePct" stroke="#ea580c" strokeWidth={2} dot={false} name="Share" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        <Card className="border-slate-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-ink-900">By engine ({multi.data.range_days}d)</h2>
          <p className="mt-1 text-xs text-slate-500">This entity’s citations ÷ all citations on that engine</p>
          <div className="mt-4 h-64">
            {barData.length === 0 ? (
              <p className="text-sm text-slate-500">No engine data.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart layout="vertical" data={barData} margin={{ top: 4, right: 16, left: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="engine" width={100} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => [`${v}%`, "Share"]} />
                  <Bar dataKey="sharePct" fill="#ea580c" radius={[0, 6, 6, 0]} maxBarSize={22} name="Share" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

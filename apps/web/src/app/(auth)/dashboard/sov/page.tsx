"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Card, ErrorState, Skeleton } from "@/components/primitives";
import { apiFetch } from "@/lib/api";

type BrandRow = { id: string; name: string; domains?: string[] };

export default function SovHubPage() {
  const brands = useQuery({
    queryKey: ["brands"],
    queryFn: async (): Promise<BrandRow[]> => {
      const r = await apiFetch("/api/v1/brands");
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
  });

  if (brands.isPending) {
    return (
      <div className="mx-auto max-w-lg space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-24 w-full rounded-xl" />
      </div>
    );
  }

  if (brands.isError) {
    return <ErrorState message="Could not load brands." onRetry={() => brands.refetch()} />;
  }

  const list = brands.data ?? [];
  if (!list.length) {
    return (
      <Card className="border-slate-100 p-6 text-sm text-slate-700">
        <p className="font-semibold text-ink-900">No brands yet</p>
        <p className="mt-2 text-slate-600">Create a brand first, then open Share of voice for that workspace.</p>
      </Card>
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink-900">Share of voice</h1>
        <p className="mt-2 text-sm text-slate-600">
          Open a brand to see citation share by engine for <strong className="font-semibold text-ink-900">your brand</strong>{" "}
          and each <strong className="font-semibold text-ink-900">linked competitor</strong> (set competitor brand IDs on
          the primary brand).
        </p>
      </div>
      <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {list.map((b) => (
          <li key={b.id}>
            <Link
              href={`/brands/${b.id}/sov`}
              className="flex items-center justify-between px-4 py-3 text-sm font-medium text-ink-900 hover:bg-slate-50"
            >
              {b.name}
              <span className="text-xs font-normal text-brand-primary">View →</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/primitives";
import { useAuthApi } from "@/hooks/useAuthApi";
import { fetchAdminStats } from "@/services/admin";

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card className="border-tr-line p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-tr-mute">{label}</p>
      <p className="mt-2 font-display text-3xl font-bold text-tr-navy">{value}</p>
    </Card>
  );
}

export default function AdminDashboardPage() {
  const api = useAuthApi();
  const stats = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => fetchAdminStats(api),
  });

  if (stats.isPending) return <p className="text-tr-mute">Loading analytics…</p>;
  if (stats.isError) return <p className="text-red-700">Could not load admin stats.</p>;

  const s = stats.data!;
  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl font-bold text-tr-navy">Dashboard</h1>
        <p className="mt-1 text-sm text-tr-mute">System overview for Citation Pulse.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard label="Total users" value={s.total_users} />
        <StatCard label="Active users" value={s.active_users} />
        <StatCard label="Total scans" value={s.total_scans} />
        <StatCard label="Completed scans" value={s.completed_scans} />
        <StatCard label="Brands" value={s.total_brands} />
      </div>
    </div>
  );
}

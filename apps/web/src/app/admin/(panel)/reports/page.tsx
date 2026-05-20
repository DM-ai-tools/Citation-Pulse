"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Card } from "@/components/primitives";
import { useAuthApi } from "@/hooks/useAuthApi";
import { fetchAdminScans } from "@/services/admin";

export default function AdminReportsPage() {
  const api = useAuthApi();
  const scans = useQuery({
    queryKey: ["admin-scans"],
    queryFn: () => fetchAdminScans(api),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-tr-navy">Reports & scans</h1>
        <p className="mt-1 text-sm text-tr-mute">All citation scans across tenants.</p>
      </div>
      <Card className="overflow-x-auto border-tr-line p-0">
        <table className="w-full text-sm">
          <thead className="border-b border-tr-line bg-tr-pale/30 text-left">
            <tr>
              <th className="p-3 font-semibold">URL</th>
              <th className="p-3 font-semibold">Status</th>
              <th className="p-3 font-semibold">Created</th>
              <th className="p-3 font-semibold">Report</th>
            </tr>
          </thead>
          <tbody>
            {(scans.data ?? []).map((s) => (
              <tr key={s.id} className="border-b border-tr-line/60">
                <td className="max-w-xs truncate p-3">{s.submitted_url}</td>
                <td className="p-3">{s.status}</td>
                <td className="p-3 text-tr-mute">
                  {s.created_at ? new Date(s.created_at).toLocaleString() : "—"}
                </td>
                <td className="p-3">
                  <Link href={`/report/${s.id}`} className="font-semibold text-brand-primary hover:underline">
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

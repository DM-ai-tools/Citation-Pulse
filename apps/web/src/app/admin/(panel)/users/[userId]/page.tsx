"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Card } from "@/components/primitives";
import { useAuthApi } from "@/hooks/useAuthApi";
import { fetchAdminUserScans } from "@/services/admin";

export default function AdminUserDetailPage() {
  const params = useParams();
  const userId = typeof params.userId === "string" ? params.userId : "";
  const api = useAuthApi();

  const detail = useQuery({
    queryKey: ["admin-user-scans", userId],
    queryFn: () => fetchAdminUserScans(api, userId),
    enabled: Boolean(userId),
  });

  if (detail.isPending) {
    return <p className="text-tr-mute">Loading user reports…</p>;
  }

  if (detail.isError || !detail.data) {
    const errMsg =
      detail.error instanceof Error ? detail.error.message : "Could not load this user's scans.";
    return (
      <div className="space-y-4">
        <Link href="/admin/users" className="inline-flex items-center gap-1 text-sm font-semibold text-brand-primary hover:underline">
          <ArrowLeft className="h-4 w-4" />
          Back to users
        </Link>
        <p className="text-red-700">{errMsg}</p>
      </div>
    );
  }

  const { user, scans } = detail.data;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/admin/users"
          className="mb-4 inline-flex items-center gap-1 text-sm font-semibold text-brand-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to users
        </Link>
        <h1 className="font-display text-2xl font-bold text-tr-navy">{user.name}</h1>
        <p className="mt-1 text-sm text-tr-mute">
          {user.email} · <span className="capitalize">{user.role}</span>
          {user.last_login_at ? ` · Last login ${new Date(user.last_login_at).toLocaleString()}` : ""}
        </p>
      </div>

      <div>
        <h2 className="font-display text-lg font-bold text-tr-navy">Scans & reports</h2>
        <p className="mt-1 text-sm text-tr-mute">
          {scans.length === 0
            ? "No scans linked to this account yet."
            : `${scans.length} scan${scans.length === 1 ? "" : "s"} for this workspace.`}
        </p>
      </div>

      {scans.length > 0 ? (
        <Card className="overflow-x-auto border-tr-line p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-tr-line bg-tr-pale/30 text-left">
              <tr>
                <th className="p-3 font-semibold text-tr-navy">URL</th>
                <th className="p-3 font-semibold text-tr-navy">Status</th>
                <th className="p-3 font-semibold text-tr-navy">Created</th>
                <th className="p-3 font-semibold text-tr-navy">Completed</th>
                <th className="p-3 font-semibold text-tr-navy">Report</th>
              </tr>
            </thead>
            <tbody>
              {scans.map((s) => (
                <tr key={s.id} className="border-b border-tr-line/60">
                  <td className="max-w-md truncate p-3" title={s.submitted_url}>
                    {s.submitted_url}
                  </td>
                  <td className="p-3 capitalize">{s.status}</td>
                  <td className="p-3 text-tr-mute whitespace-nowrap">
                    {s.created_at ? new Date(s.created_at).toLocaleString() : "—"}
                  </td>
                  <td className="p-3 text-tr-mute whitespace-nowrap">
                    {s.completed_at ? new Date(s.completed_at).toLocaleString() : "—"}
                  </td>
                  <td className="p-3">
                    <Link href={`/report/${s.id}`} className="font-semibold text-brand-primary hover:underline">
                      View report
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : (
        <Card className="border-tr-line p-6 text-sm text-tr-mute">
          This user has no scans in their workspace. Scans run before sign-up or without a tenant are not listed here.
        </Card>
      )}
    </div>
  );
}

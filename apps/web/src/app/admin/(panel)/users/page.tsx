"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, Input } from "@/components/primitives";
import { useAuthApi } from "@/hooks/useAuthApi";
import { fetchAdminUsers } from "@/services/admin";

export default function AdminUsersPage() {
  const router = useRouter();
  const api = useAuthApi();
  const [q, setQ] = useState("");
  const users = useQuery({
    queryKey: ["admin-users", q],
    queryFn: () => fetchAdminUsers(api, q || undefined),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-tr-navy">Users</h1>
        <p className="mt-1 text-sm text-tr-mute">Click a user to view all scans and reports for their workspace.</p>
      </div>
      <Input placeholder="Search by name or email…" value={q} onChange={(e) => setQ(e.target.value)} />
      <Card className="overflow-x-auto border-tr-line p-0">
        <table className="w-full text-sm">
          <thead className="border-b border-tr-line bg-tr-pale/30 text-left">
            <tr>
              <th className="p-3 font-semibold text-tr-navy">Name</th>
              <th className="p-3 font-semibold text-tr-navy">Email</th>
              <th className="p-3 font-semibold text-tr-navy">Role</th>
              <th className="p-3 font-semibold text-tr-navy">Last login</th>
            </tr>
          </thead>
          <tbody>
            {(users.data ?? []).map((u) => (
              <tr
                key={u.id}
                className="cursor-pointer border-b border-tr-line/60 transition hover:bg-tr-pale/40"
                onClick={() => router.push(`/admin/users/${u.id}`)}
              >
                <td className="p-3 font-medium text-tr-navy">{u.name}</td>
                <td className="p-3">{u.email}</td>
                <td className="p-3 capitalize">{u.role}</td>
                <td className="p-3 text-tr-mute">
                  {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

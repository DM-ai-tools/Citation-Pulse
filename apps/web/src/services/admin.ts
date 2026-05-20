import type { ApiClientOptions } from "@/services/apiClient";

export type AdminStats = {
  total_users: number;
  active_users: number;
  total_scans: number;
  completed_scans: number;
  total_brands: number;
};

export type AdminUserRow = {
  id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type AdminScanRow = {
  id: string;
  status: string;
  submitted_url: string;
  brand_id: string | null;
  created_at: string | null;
  completed_at: string | null;
};

export async function fetchAdminStats(
  api: (path: string, init?: ApiClientOptions) => Promise<Response>,
) {
  const r = await api("/api/v1/admin/stats");
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as AdminStats;
}

export async function fetchAdminUsers(
  api: (path: string, init?: ApiClientOptions) => Promise<Response>,
  q?: string,
) {
  const r = await api(`/api/v1/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as AdminUserRow[];
}

export async function fetchAdminScans(api: (path: string, init?: ApiClientOptions) => Promise<Response>) {
  const r = await api("/api/v1/admin/scans?limit=100");
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as AdminScanRow[];
}

export type AdminUserScansResponse = {
  user: AdminUserRow;
  scans: AdminScanRow[];
};

export async function fetchAdminUserScans(
  api: (path: string, init?: ApiClientOptions) => Promise<Response>,
  userId: string,
) {
  const r = await api(`/api/v1/admin/users/${userId}/scans`);
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as AdminUserScansResponse;
}

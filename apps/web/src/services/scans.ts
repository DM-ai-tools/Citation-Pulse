import { apiFetch, publicApiBaseUrl } from "./apiClient";
import type { ReportData } from "@/types/report";
import type { ScanSnapshot } from "@/types/scan";

const scanPostTimeoutMs = 60_000;

export async function createScan(body: {
  url: string;
  competitors?: string[];
  prompts: string[];
  locale: string;
  engines?: string[];
  auto_discover_competitors?: boolean;
  service?: string;
  niche?: string;
  location?: string;
}): Promise<{ scan_id: string }> {
  const r = await apiFetch("/api/v1/scans", {
    method: "POST",
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(scanPostTimeoutMs),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

export async function getScan(scanId: string): Promise<ScanSnapshot> {
  const r = await apiFetch(`/api/v1/scans/${scanId}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getScanReport(scanId: string): Promise<ReportData> {
  const r = await apiFetch(`/api/v1/scans/${scanId}/report`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function shareScan(scanId: string, share_public = true) {
  const r = await apiFetch(`/api/v1/scans/${scanId}/share`, {
    method: "POST",
    body: JSON.stringify({ share_public }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ share_token: string | null; share_public: boolean }>;
}

export function scanStreamUrl(scanId: string) {
  return `${publicApiBaseUrl()}/api/v1/scans/${scanId}/stream`;
}

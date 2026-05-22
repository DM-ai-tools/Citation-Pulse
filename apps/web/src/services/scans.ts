import { formatApiErrorBody } from "@/lib/apiErrors";
import { isAuthBypass } from "@/lib/authBypass";
import { apiClient, apiFetch, publicApiBaseUrl } from "./apiClient";
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
  const r = await apiClient("/api/v1/scans/", {
    method: "POST",
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(scanPostTimeoutMs),
    auth: !isAuthBypass(),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(formatApiErrorBody(r.status, t) || r.statusText);
  }
  return r.json();
}

export async function getScan(scanId: string): Promise<ScanSnapshot> {
  const r = await apiFetch(`/api/v1/scans/${scanId}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getScanReport(scanId: string, options?: { lite?: boolean }): Promise<ReportData> {
  const lite = options?.lite ? "?lite=true" : "";
  const r = await apiFetch(`/api/v1/scans/${encodeURIComponent(scanId)}/report${lite}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type CompetitorCitationsPayload = {
  competitor_citation_visibility: ReportData["competitor_citation_visibility"];
  competitor_discovery: ReportData["competitor_discovery"];
  competitor_discovery_pending?: boolean;
  validation_complete?: boolean;
};

/** Lightweight poll target while full report (SoV) loads. */
export async function getScanCompetitorCitations(scanId: string): Promise<CompetitorCitationsPayload> {
  const r = await apiFetch(`/api/v1/scans/${encodeURIComponent(scanId)}/competitor-citations`);
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

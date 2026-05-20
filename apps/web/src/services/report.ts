import { publicApiFetch } from "./apiClient";
import type { ReportData } from "@/types/report";

export async function getPublicReport(token: string): Promise<ReportData> {
  const r = await publicApiFetch(`/api/v1/scans/public/${encodeURIComponent(token)}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

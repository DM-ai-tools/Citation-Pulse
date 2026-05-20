"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthApi } from "@/hooks/useAuthApi";
import { DASHBOARD_LAST_SCAN_STORAGE_KEY } from "@/lib/dashboardScanPreference";
import { getScanReport } from "@/services/scans";
import type { ReportData } from "@/types/report";

const SCAN_ID_FROM_ENV = process.env.NEXT_PUBLIC_DASHBOARD_SCAN_ID?.trim() ?? "";
const BRAND_ID_ENV = process.env.NEXT_PUBLIC_DASHBOARD_BRAND_ID?.trim() ?? "";
const SITE_URL_ENV = process.env.NEXT_PUBLIC_DASHBOARD_SITE_URL?.trim() ?? "";

export type DashboardBrandRow = { id: string; name: string; domains?: string[] };

function normalizeSiteHost(raw: string): string {
  const t = raw.trim();
  if (!t) return "";
  try {
    const u = t.includes("://") ? new URL(t) : new URL(`https://${t}`);
    return u.hostname.replace(/^www\./i, "").toLowerCase();
  } catch {
    return t
      .replace(/^https?:\/\//i, "")
      .replace(/^www\./i, "")
      .split("/")[0]
      ?.toLowerCase() ?? "";
  }
}

function brandMatchesSiteUrl(b: DashboardBrandRow, siteRaw: string): boolean {
  const want = normalizeSiteHost(siteRaw);
  if (!want) return false;
  if (normalizeSiteHost(b.name) === want) return true;
  for (const d of b.domains ?? []) {
    if (normalizeSiteHost(d) === want) return true;
  }
  return false;
}

function pickBrandId(list: DashboardBrandRow[]): string {
  if (BRAND_ID_ENV) return BRAND_ID_ENV;
  if (SITE_URL_ENV && list.length > 0) {
    const hit = list.find((b) => brandMatchesSiteUrl(b, SITE_URL_ENV));
    if (hit) return hit.id;
  }
  return list[0]?.id ?? "";
}

/**
 * Workspace data for /dashboard and /dashboard/gaps.
 * Prefers the latest landing scan report (localStorage) when available; otherwise tenant brands.
 */
export function useDashboardWorkspace() {
  const authApi = useAuthApi();
  const [storedScanId, setStoredScanId] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (SCAN_ID_FROM_ENV) {
      setReady(true);
      return;
    }
    try {
      setStoredScanId(localStorage.getItem(DASHBOARD_LAST_SCAN_STORAGE_KEY)?.trim() ?? "");
    } catch {
      setStoredScanId("");
    }
    setReady(true);
  }, []);

  const effectiveScanId = SCAN_ID_FROM_ENV || storedScanId;
  const hasScanPin = Boolean(effectiveScanId);

  const report = useQuery({
    queryKey: ["dashboard-scan-report", effectiveScanId],
    queryFn: () => getScanReport(effectiveScanId),
    enabled: ready && hasScanPin,
  });

  const brands = useQuery({
    queryKey: ["brands"],
    queryFn: async (): Promise<DashboardBrandRow[]> => {
      const r = await authApi("/api/v1/brands");
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    enabled: ready,
  });

  const tenantBrands = brands.data ?? [];

  /** Use citation report when a scan id exists and the report loaded (same data as /report/[id]). */
  const useScanReport = hasScanPin && Boolean(report.data) && !report.isError;

  const brandId = useMemo(() => {
    if (useScanReport) {
      return report.data?.brand?.id ?? report.data?.opportunities?.[0]?.brand_id ?? "";
    }
    return pickBrandId(tenantBrands);
  }, [useScanReport, report.data, tenantBrands]);

  const brandName = useMemo(() => {
    if (useScanReport && report.data) {
      return report.data.brand?.name ?? report.data.submitted_url ?? "Your scan";
    }
    return tenantBrands.find((b) => b.id === brandId)?.name ?? "Brand";
  }, [useScanReport, report.data, tenantBrands, brandId]);

  const isLoading =
    !ready || (hasScanPin && report.isPending && !report.data) || (!useScanReport && brands.isPending);

  const isError = hasScanPin ? report.isError && tenantBrands.length === 0 : brands.isError;

  return {
    ready,
    effectiveScanId,
    hasScanPin,
    useScanReport,
    report: report.data as ReportData | undefined,
    brandId,
    brandName,
    tenantBrands,
    isLoading,
    isError,
    linkedFromLanding: hasScanPin && !SCAN_ID_FROM_ENV,
    refetch: () => {
      if (hasScanPin) void report.refetch();
      void brands.refetch();
    },
  };
}

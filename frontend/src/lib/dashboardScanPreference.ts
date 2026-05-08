/** Persists the user's latest landing / live scan so the workspace dashboard can load the same report (incl. SoV). */

export const DASHBOARD_LAST_SCAN_STORAGE_KEY = "citationpulse:lastScanId";
export const DASHBOARD_LAST_URL_STORAGE_KEY = "citationpulse:lastSubmittedUrl";

export function rememberDashboardScan(scanId: string, submittedUrl?: string) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(DASHBOARD_LAST_SCAN_STORAGE_KEY, scanId);
    if (submittedUrl?.trim()) {
      localStorage.setItem(DASHBOARD_LAST_URL_STORAGE_KEY, submittedUrl.trim());
    }
  } catch {
    /* ignore quota / private mode */
  }
}

"use client";

import { useEffect, useState } from "react";
import { publicApiBaseUrl } from "@/services/apiClient";
import type { ScanSnapshot } from "@/types/scan";
import { matrixAllCellsQueued } from "@/lib/matrixStats";

const STALL_MS = 45_000;

export function ScanStallNotice({ data }: { data: ScanSnapshot }) {
  const [stalled, setStalled] = useState(false);

  useEffect(() => {
    const active = data.status === "queued" || data.status === "running";
    const allQueued = matrixAllCellsQueued(data.prompts, data.engines, data.matrix.cells);
    if (!active || !allQueued) {
      setStalled(false);
      return;
    }
    const id = window.setTimeout(() => setStalled(true), STALL_MS);
    return () => window.clearTimeout(id);
  }, [data.status, data.prompts, data.engines, data.matrix.cells]);

  if (!stalled) return null;

  const api = publicApiBaseUrl();

  return (
    <div
      role="alert"
      className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
    >
      <p className="font-semibold">Scan is not progressing</p>
      <p className="mt-1 leading-relaxed">
        All checks are still queued. This is usually a <strong>backend</strong> issue (Celery tasks not
        running), not the web app. Redeploy the API from latest <code className="text-xs">main</code>,
        confirm <code className="text-xs">GET {api}/health</code> returns OK, then start a new scan.
      </p>
      <p className="mt-2 text-xs text-amber-900/80">
        Railway Web logs only show page loads (e.g. <code>/scan/…</code>, <code>/favicon.ico</code>).
        API traffic goes to <code className="break-all">{api}</code> — check that service&apos;s deploy
        logs for errors.
      </p>
    </div>
  );
}

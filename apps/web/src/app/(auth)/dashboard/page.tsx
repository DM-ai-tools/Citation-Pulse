"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { useQuery } from "@tanstack/react-query";
import { Fragment, useEffect, useId, useMemo, useState, type ReactNode } from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  createColumnHelper,
} from "@tanstack/react-table";
import { ExternalLink } from "lucide-react";
import { Card, ErrorState, Skeleton } from "@/components/primitives";
import { CitationHeatmap } from "@/components/report/CitationHeatmap";
import { TopGapOpportunities } from "@/components/report/TopGapOpportunities";
import { CompetitorRoster } from "@/components/report/CompetitorRoster";
import { CompetitorDiscovery } from "@/components/report/CompetitorDiscovery";
import { CompetitorEngineCitations } from "@/components/report/CompetitorEngineCitations";
import { rosterFromReport } from "@/lib/competitorRoster";
import { apiFetch } from "@/lib/api";
import { DASHBOARD_LAST_SCAN_STORAGE_KEY } from "@/lib/dashboardScanPreference";
import { engineTitle } from "@/lib/engineDisplay";
import { getBrandOpportunities } from "@/services/brands";
import { getScanReport } from "@/services/scans";
import type { OpportunityRow, ReportData } from "@/types/report";
import type { MatrixCell } from "@/types/scan";

type CitationRow = { id: string; url: string; domain: string; ownership: string };

type BrandRow = { id: string; name: string; domains?: string[] };

type BrandProfile = { id: string; name: string; domains: string[] };

type WebsiteSummary = {
  primaryHref: string;
  primaryHost: string;
  allHosts: string[];
  /** Scan flow: URL that was analyzed */
  submittedFull?: string;
};

type MatrixBundle = {
  prompts: { id: string; text: string; locale: string }[];
  engines: string[];
  matrix: { cells: MatrixCell[] };
};

type SoVResponse = { brand_share: number; range_days: number };

/** Optional: set in Docker/Railway build to show deploy revision on the dashboard (e.g. git SHA). */
const APP_BUILD_LABEL = process.env.NEXT_PUBLIC_APP_VERSION?.trim() ?? "";

/** Deploy-time override; otherwise the latest landing-page scan id from localStorage is used. */
const SCAN_ID_FROM_ENV = process.env.NEXT_PUBLIC_DASHBOARD_SCAN_ID?.trim() ?? "";
const BRAND_ID_ENV = process.env.NEXT_PUBLIC_DASHBOARD_BRAND_ID?.trim() ?? "";
/** Match this site (e.g. firstpage.com.au or https://www.firstpage.com.au) to pick the brand when multiple exist */
const SITE_URL_ENV = process.env.NEXT_PUBLIC_DASHBOARD_SITE_URL?.trim() ?? "";

function urlHostFromSubmitted(submitted: string): string {
  return submitted.replace(/^https?:\/\//, "").split("/")[0] ?? "";
}

/** Normalize to registrable host for comparisons (no scheme, no path, lowercase). */
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

function brandMatchesSiteUrl(b: BrandRow, siteRaw: string): boolean {
  const want = normalizeSiteHost(siteRaw);
  if (!want) return false;
  if (normalizeSiteHost(b.name) === want) return true;
  for (const d of b.domains ?? []) {
    if (normalizeSiteHost(d) === want) return true;
  }
  return false;
}

function websiteFromBrand(name: string, domains: string[]): WebsiteSummary | null {
  const hosts = [...new Set((domains ?? []).map(normalizeSiteHost).filter(Boolean))];
  const fallback = normalizeSiteHost(name);
  const primaryHost = hosts[0] ?? fallback;
  if (!primaryHost) return null;
  const allHosts = hosts.length > 0 ? hosts : [primaryHost];
  return {
    primaryHref: `https://${primaryHost}`,
    primaryHost,
    allHosts,
  };
}

function websiteFromScanReport(data: ReportData): WebsiteSummary | null {
  const submitted = data.submitted_url?.trim() ?? "";
  const brandDomains = data.brand?.domains ?? [];
  const normalizedScanHost = submitted ? normalizeSiteHost(urlHostFromSubmitted(submitted)) : "";
  const mergedHosts = [
    ...new Set([normalizedScanHost, ...brandDomains.map(normalizeSiteHost)].filter(Boolean)),
  ];
  const primaryHost = normalizedScanHost || mergedHosts[0] || "";
  if (!primaryHost) return null;

  let primaryHref: string;
  if (submitted.startsWith("http")) {
    primaryHref = submitted;
  } else if (submitted) {
    primaryHref = `https://${normalizedScanHost || primaryHost}`;
  } else {
    primaryHref = `https://${primaryHost}`;
  }

  return {
    primaryHref,
    primaryHost,
    allHosts: mergedHosts.length > 0 ? mergedHosts : [primaryHost],
    submittedFull: submitted || undefined,
  };
}

function domainFromUrl(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.slice(0, 80);
  }
}

function citationsFromMatrixCells(cells: MatrixCell[]): CitationRow[] {
  const rows: CitationRow[] = [];
  let i = 0;
  for (const cell of cells) {
    for (const c of cell.citations ?? []) {
      rows.push({
        id: `${cell.promptId}-${cell.engine}-${i++}`,
        url: c.url,
        domain: domainFromUrl(c.url),
        ownership: String(c.ownership),
      });
    }
  }
  return rows;
}

function totalCitationsInMatrix(cells: MatrixCell[]): number {
  let n = 0;
  for (const c of cells) {
    n += c.citationsCount ?? (c.citations?.length ?? 0);
  }
  return n;
}

function engineMixFromMatrix(cells: MatrixCell[], engines: string[]): { engine: string; citations: number }[] {
  const counts = new Map<string, number>();
  for (const e of engines) counts.set(e, 0);
  for (const c of cells) {
    const add = c.citationsCount ?? (c.citations?.length ?? 0);
    counts.set(c.engine, (counts.get(c.engine) ?? 0) + add);
  }
  return engines.map((engine) => ({
    engine: engineTitle(engine),
    citations: counts.get(engine) ?? 0,
  }));
}

function EngineMixTooltip({ active, payload, label }: TooltipProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null;
  const n = Number(payload[0]?.value);
  return (
    <div className="rounded-xl border border-tr-line bg-white px-4 py-3 shadow-lift">
      <p className="font-display text-[10px] font-extrabold uppercase tracking-wide text-tr-mute">{label}</p>
      <p className="mt-1 font-display text-lg font-black tabular-nums text-tr-navy">
        {n}
        <span className="text-sm font-semibold text-tr-mute"> citations</span>
      </p>
    </div>
  );
}

function DeployFootnote() {
  if (!APP_BUILD_LABEL) return null;
  return (
    <p className="mt-6 text-center text-[11px] text-slate-400" data-testid="app-build-label">
      App build: {APP_BUILD_LABEL}
    </p>
  );
}

function SkeletonDashboard() {
  return (
    <div className="space-y-8">
      <Skeleton className="h-16 w-full max-w-xl rounded-xl" />
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
      </div>
      <Skeleton className="h-[420px] w-full rounded-2xl" />
    </div>
  );
}

function DashboardShell(props: {
  brandDisplayName: string;
  website: WebsiteSummary | null;
  headerMeta: ReactNode;
  sovPct: string;
  sovFootnote: string;
  citationTotal: number;
  citationLabel: string;
  citationFootnote: string;
  prompts: { id: string; text: string }[];
  engines: string[];
  cells: MatrixCell[];
  chartRows: { engine: string; citations: number }[];
  mixTitle: string;
  mixFootnote: string;
  tableRows: CitationRow[];
  /** Rendered after matrix / engine mix, before the citations URL table. */
  beforeCitations?: ReactNode;
}) {
  const barGradientId = useId().replace(/:/g, "");
  const columns = useMemo(() => {
    const ch = createColumnHelper<CitationRow>();
    return [
      ch.accessor("domain", { header: "Domain" }),
      ch.accessor("url", { header: "URL", cell: (i) => String(i.getValue()).slice(0, 80) }),
      ch.accessor("ownership", { header: "Owner" }),
    ];
  }, []);

  const table = useReactTable({
    data: props.tableRows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const mixTotal = props.chartRows.reduce((s, r) => s + r.citations, 0);

  return (
    <div className="space-y-8">
      <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Brand</p>
        <p className="mt-1 text-lg font-semibold text-ink-900">{props.brandDisplayName}</p>
        {props.website ? (
          <div className="mt-4 border-t border-slate-100 pt-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your website</p>
            <a
              href={props.website.primaryHref}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-flex items-center gap-1.5 text-[15px] font-semibold text-brand-primary hover:underline"
            >
              {props.website.primaryHref}
              <ExternalLink className="h-4 w-4 shrink-0 opacity-70" aria-hidden />
            </a>
            <p className="mt-0.5 font-mono text-xs text-slate-500">{props.website.primaryHost}</p>
            {props.website.submittedFull &&
            normalizeSiteHost(props.website.submittedFull) !== props.website.primaryHost ? (
              <p className="mt-2 text-xs text-slate-500">
                Scan URL: <span className="font-mono text-ink-800">{props.website.submittedFull}</span>
              </p>
            ) : null}
            {props.website.allHosts.length > 1 ? (
              <div className="mt-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Domains on file</p>
                <ul className="mt-1.5 flex flex-wrap gap-2">
                  {props.website.allHosts.map((h) => (
                    <li
                      key={h}
                      className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 font-mono text-xs text-slate-700"
                    >
                      {h}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
        {props.headerMeta}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border-slate-100">
          <p className="text-sm text-slate-500">Brand SoV (30d)</p>
          <p className="mt-2 text-2xl font-bold text-ink-900">{props.sovPct}</p>
          <p className="mt-1 text-xs text-slate-400">{props.sovFootnote}</p>
        </Card>
        <Card className="border-slate-100">
          <p className="text-sm text-slate-500">{props.citationLabel}</p>
          <p className="mt-2 text-2xl font-bold text-ink-900">{props.citationTotal}</p>
          <p className="mt-1 text-xs text-slate-400">{props.citationFootnote}</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-stretch lg:gap-8">
        <section className="min-w-0 lg:w-full">
          {props.prompts.length > 0 ? (
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-ink-900">Citation matrix</h2>
              <p className="text-sm text-slate-500">
                Engine × prompt cells — same scoring model as the citation report for this workspace view.
              </p>
              <CitationHeatmap
                prompts={props.prompts.map((p) => ({ id: p.id, text: p.text }))}
                engines={props.engines}
                cells={props.cells}
                mode="final"
                visual="tiles"
                title="Engine × prompt"
              />
            </div>
          ) : (
            <Card className="h-full border-slate-100 p-6 text-sm text-slate-600">
              No prompts for this brand yet — add prompts to see the matrix.
            </Card>
          )}
        </section>

        <section className="min-w-0 lg:w-full">
          <Card className="flex h-full min-h-[320px] flex-col border-tr-line/80 bg-gradient-to-b from-white via-white to-tr-pale/40 shadow-card">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="font-display text-lg font-bold tracking-tight text-tr-navy">{props.mixTitle}</h2>
                <p className="mt-1 text-sm text-tr-mute">
                  {props.mixFootnote}{" "}
                  <span className="font-semibold text-tr-teal">({mixTotal} total)</span>.
                </p>
              </div>
            </div>
            <div className="mt-4 h-[260px] rounded-xl border border-tr-line/50 bg-white/60 px-1 pt-3 pb-1 sm:h-[280px] sm:px-2 sm:pt-4 sm:pb-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={props.chartRows.length ? props.chartRows : [{ engine: "—", citations: 0 }]}
                  margin={{ top: 8, right: 4, left: -12, bottom: 4 }}
                  barCategoryGap="18%"
                >
                  <defs>
                    <linearGradient id={barGradientId} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#32D882" stopOpacity={0.95} />
                      <stop offset="55%" stopColor="#1FB36B" stopOpacity={1} />
                      <stop offset="100%" stopColor="#18965A" stopOpacity={1} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="4 6"
                    stroke="#D7EBDD"
                    strokeOpacity={0.85}
                    vertical={false}
                  />
                  <XAxis
                    dataKey="engine"
                    tick={{ fontSize: 10, fill: "#6B7A88", fontFamily: "var(--font-dm), system-ui, sans-serif" }}
                    tickLine={false}
                    axisLine={{ stroke: "#D7EBDD" }}
                    interval={0}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 10, fill: "#6B7A88", fontFamily: "var(--font-dm), system-ui, sans-serif" }}
                    tickLine={false}
                    axisLine={false}
                    width={32}
                  />
                  <Tooltip
                    cursor={{ fill: "rgba(31, 179, 107, 0.10)" }}
                    content={(tipProps) => <EngineMixTooltip {...(tipProps as TooltipProps<ValueType, NameType>)} />}
                  />
                  <Bar
                    dataKey="citations"
                    fill={`url(#${barGradientId})`}
                    radius={[10, 10, 4, 4]}
                    maxBarSize={48}
                    animationDuration={600}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </section>
      </div>

      {props.beforeCitations}

      <Card className="overflow-x-auto border-slate-100">
        <h2 className="text-lg font-semibold text-ink-900">Citations</h2>
        <p className="mt-1 text-sm text-slate-500">URLs surfaced from the matrix cells below.</p>
        <table className="mt-4 w-full text-sm">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-slate-100 text-left">
                {hg.headers.map((h) => (
                  <th key={h.id} className="p-2 font-semibold text-slate-600">
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={3} className="p-4 text-slate-500">
                  No citation URLs in the matrix yet.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="border-b border-slate-50">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="p-2 text-ink-800">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function ScanDashboard({ data, linkedFromLanding }: { data: ReportData; linkedFromLanding?: boolean }) {
  const cells = data.matrix.cells ?? [];
  const engines = data.engines ?? [];
  const chartRows = engineMixFromMatrix(cells, engines);
  const tableRows = citationsFromMatrixCells(cells);
  const roster = rosterFromReport(data);
  const sovPct =
    data.breakdown != null ? `${Math.round(data.breakdown.brand_share * 100)}%` : "—";
  const brandDisplayName = data.brand?.name ?? urlHostFromSubmitted(data.submitted_url);
  const website = websiteFromScanReport(data);

  return (
    <DashboardShell
        brandDisplayName={brandDisplayName}
        website={website}
        headerMeta={
          <>
            <p className="mt-1 font-mono text-xs text-slate-400">Scan {data.scan_id}</p>
            {linkedFromLanding ? (
              <p className="mt-2 text-xs text-slate-600">
                SoV and KPIs match your citation report for the site you submitted on the landing page. Run a new scan
                there anytime to refresh this workspace view.
              </p>
            ) : null}
          </>
        }
        sovPct={sovPct}
        sovFootnote="Same 30-day breakdown as the citation report for this scan."
        citationTotal={totalCitationsInMatrix(cells)}
        citationLabel="Citations (this scan)"
        citationFootnote="Citation rows attached to this scan’s matrix cells."
        prompts={data.prompts}
        engines={engines}
        cells={cells}
        chartRows={chartRows}
        mixTitle="Engine mix (this scan)"
        mixFootnote="Citations captured per engine from the matrix above"
        tableRows={tableRows}
        beforeCitations={
          <div className="max-w-6xl space-y-6">
            {(roster.userProvided.length > 0 || roster.analysis.length > 0) ? (
              <Card className="border-tr-line p-5">
                <h2 className="font-display text-lg font-bold text-tr-navy">Tracked competitors</h2>
                <p className="mt-1 text-sm text-tr-mute">
                  AI analysis and companies you entered — scroll to browse.
                </p>
                <div className="mt-4 max-h-[280px] overflow-y-auto overflow-x-hidden pr-1 scroll-smooth">
                  <CompetitorRoster
                    analysis={roster.analysis}
                    userProvided={roster.userProvided}
                    variant="dashboard"
                  />
                </div>
              </Card>
            ) : null}
            <CompetitorDiscovery
              discovery={data.competitor_discovery}
              userProvided={roster.userProvided}
              analysisCompetitors={roster.analysis}
              scanStatus={data.status}
              pending={Boolean(data.competitor_discovery_pending)}
            />
            <CompetitorEngineCitations
              data={data.competitor_citation_visibility}
              prompts={data.prompts}
              discoveryPending={Boolean(data.competitor_discovery_pending)}
              discoveryFailed={
                !data.competitor_discovery &&
                !data.competitor_discovery_pending &&
                (data.competitor_discovery_status === "failed" ||
                  data.competitor_discovery_status === "skipped")
              }
            />
            <TopGapOpportunities opportunities={data.opportunities ?? []} />
          </div>
        }
      />
  );
}

function BrandDashboard(props: {
  brandName: string;
  website: WebsiteSummary | null;
  matrix: MatrixBundle;
  sov: SoVResponse | null;
  opportunities: OpportunityRow[];
}) {
  const cells = props.matrix.matrix.cells ?? [];
  const engines = props.matrix.engines ?? [];
  const chartRows = engineMixFromMatrix(cells, engines);
  const tableRows = citationsFromMatrixCells(cells);
  const sovPct =
    props.sov != null ? `${Math.round((props.sov.brand_share ?? 0) * 100)}%` : "—";

  return (
    <Fragment>
      <DashboardShell
        brandDisplayName={props.brandName}
        website={props.website}
        headerMeta={
          <div className="space-y-3">
            <div className="rounded-lg border border-amber-200/90 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-950">
              <strong className="font-semibold">Workspace view:</strong> SoV and the matrix use this brand&apos;s
              30‑day runs. <strong className="font-semibold">Top gap opportunities</strong> (above the citations table)
              load from the same saved detection data as the API (<code className="rounded bg-white/80 px-1 font-mono text-[11px]">
                GET /brands/…/opportunities
              </code>
              ), not from a funnel scan id. Run a free scan from the home page to store a last scan in this browser, or
              set <code className="font-mono text-[11px]">NEXT_PUBLIC_DASHBOARD_SCAN_ID</code> on the web host to pin
              the live report view.
            </div>
            <p className="text-xs text-slate-500">
              When multiple brands exist, optionally set{" "}
              <code className="font-mono text-[11px]">NEXT_PUBLIC_DASHBOARD_SITE_URL</code> to match the site you care
              about.
            </p>
          </div>
        }
        sovPct={sovPct}
        sovFootnote={`Share of brand-owned citations from finished runs in the last ${props.sov?.range_days ?? 30} days.`}
        citationTotal={totalCitationsInMatrix(cells)}
        citationLabel="Citations (matrix)"
        citationFootnote="Total citation rows in the 30-day prompt × engine matrix."
        prompts={props.matrix.prompts}
        engines={engines}
        cells={cells}
        chartRows={chartRows}
        mixTitle="Engine mix (matrix)"
        mixFootnote="Citations captured per engine from the matrix above"
        tableRows={tableRows}
        beforeCitations={
          <div className="max-w-6xl">
            <TopGapOpportunities opportunities={props.opportunities} />
          </div>
        }
      />
      <DeployFootnote />
    </Fragment>
  );
}

export default function DashboardPage() {
  const [storedScanId, setStoredScanId] = useState("");
  const [scanPrefReady, setScanPrefReady] = useState(false);

  useEffect(() => {
    if (SCAN_ID_FROM_ENV) {
      setScanPrefReady(true);
      return;
    }
    try {
      setStoredScanId(localStorage.getItem(DASHBOARD_LAST_SCAN_STORAGE_KEY)?.trim() ?? "");
    } catch {
      setStoredScanId("");
    }
    setScanPrefReady(true);
  }, []);

  const effectiveScanId = SCAN_ID_FROM_ENV || storedScanId;
  const useScanReport = Boolean(effectiveScanId);

  const brands = useQuery({
    queryKey: ["brands"],
    queryFn: async (): Promise<BrandRow[]> => {
      const r = await apiFetch("/api/v1/brands");
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    enabled: scanPrefReady && !useScanReport,
  });

  const effectiveBrandId = useMemo(() => {
    if (useScanReport) return "";
    if (BRAND_ID_ENV) return BRAND_ID_ENV;
    const list = brands.data ?? [];
    if (SITE_URL_ENV && list.length > 0) {
      const hit = list.find((b) => brandMatchesSiteUrl(b, SITE_URL_ENV));
      if (hit) return hit.id;
    }
    return list[0]?.id ?? "";
  }, [brands.data, useScanReport]);

  const report = useQuery({
    queryKey: ["dashboard-scan-report", effectiveScanId],
    queryFn: () => getScanReport(effectiveScanId),
    enabled: scanPrefReady && useScanReport,
  });

  const brandProfile = useQuery({
    queryKey: ["brand-profile", effectiveBrandId],
    queryFn: async (): Promise<BrandProfile> => {
      const r = await apiFetch(`/api/v1/brands/${effectiveBrandId}`);
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    enabled: scanPrefReady && !useScanReport && !!effectiveBrandId,
  });

  const sov = useQuery({
    queryKey: ["sov", effectiveBrandId],
    queryFn: async (): Promise<SoVResponse | null> => {
      const r = await apiFetch(`/api/v1/brands/${effectiveBrandId}/sov?range=30d`);
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    enabled: scanPrefReady && !useScanReport && !!effectiveBrandId,
  });

  const matrix = useQuery({
    queryKey: ["matrix", effectiveBrandId],
    queryFn: async (): Promise<MatrixBundle | null> => {
      const r = await apiFetch(`/api/v1/brands/${effectiveBrandId}/matrix?range=30d`);
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    enabled: scanPrefReady && !useScanReport && !!effectiveBrandId,
  });

  const brandOpportunities = useQuery({
    queryKey: ["brand-opportunities", effectiveBrandId],
    queryFn: () => getBrandOpportunities(effectiveBrandId),
    enabled: scanPrefReady && !useScanReport && !!effectiveBrandId,
    retry: 1,
  });

  /* ---------- Scan mode (env or latest landing scan) ---------- */
  if (!scanPrefReady) {
    return <SkeletonDashboard />;
  }

  if (useScanReport) {
    if (report.isPending) return <SkeletonDashboard />;
    if (report.isError || !report.data) {
      return (
        <ErrorState
          message="Could not load this scan report. Run a free scan from the landing page, or set NEXT_PUBLIC_DASHBOARD_SCAN_ID. Ensure you are signed in to the same workspace."
          onRetry={() => report.refetch()}
        />
      );
    }
    return (
      <div>
        <ScanDashboard data={report.data} linkedFromLanding={!SCAN_ID_FROM_ENV && Boolean(storedScanId)} />
        <DeployFootnote />
      </div>
    );
  }

  /* ---------- Brand mode (default) ---------- */
  if (brands.isPending) return <SkeletonDashboard />;
  if (brands.isError) {
    return (
      <ErrorState message="Could not load brands — check NEXT_PUBLIC_API_URL and that the API is running." onRetry={() => brands.refetch()} />
    );
  }
  if (!brands.data?.length) {
    return (
      <Card className="border-slate-100 p-6 text-sm text-slate-700">
        <p className="font-semibold text-ink-900">No brands yet</p>
        <p className="mt-2 text-slate-600">
          Create a brand with <code className="rounded bg-slate-100 px-1 font-mono text-xs">POST /api/v1/brands</code>{" "}
          to populate this dashboard.
        </p>
      </Card>
    );
  }

  if (!effectiveBrandId) return <SkeletonDashboard />;

  const brandKpisLoading = brandProfile.isPending || sov.isPending || matrix.isPending;

  if (brandKpisLoading) return <SkeletonDashboard />;

  if (brandProfile.isError || sov.isError || matrix.isError || !matrix.data) {
    const retry = () => {
      void brandProfile.refetch();
      void sov.refetch();
      void matrix.refetch();
    };
    return (
      <ErrorState
        message="Dashboard data failed to load. Confirm the brand exists for your tenant and the API is healthy."
        onRetry={retry}
      />
    );
  }

  const brandName = brandProfile.data?.name ?? "Brand";
  const websiteSummary = websiteFromBrand(brandName, brandProfile.data?.domains ?? []);
  const opportunityRows: OpportunityRow[] = brandOpportunities.data ?? [];

  return (
    <BrandDashboard
      brandName={brandName}
      website={websiteSummary}
      matrix={matrix.data}
      sov={sov.data}
      opportunities={opportunityRows}
    />
  );
}


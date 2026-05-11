"use client";

import type { FormEvent, KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Select } from "@/components/primitives";
import { cn } from "@/lib/utils";
import { rememberDashboardScan } from "@/lib/dashboardScanPreference";
import { scanFormSchema } from "@/lib/validation";
import { createScan } from "@/services/scans";

function truncate(s: string, n: number) {
  return s.length <= n ? s : `${s.slice(0, n)}…`;
}

const MAX_PROMPTS = 8;
const MAX_COMPETITORS = 5;

function normalizeDomainToken(raw: string): string {
  let t = raw.trim();
  if (!t) return "";
  if (/^https?:\/\//i.test(t)) {
    try {
      const u = new URL(t);
      t = u.hostname;
    } catch {
      t = t.replace(/^https?:\/\//i, "").split("/")[0] ?? t;
    }
  } else {
    t = t.split("/")[0]?.split("?")[0] ?? t;
  }
  t = t.replace(/^www\./i, "");
  return t.trim();
}

function domainDedupeKey(s: string) {
  return s.toLowerCase();
}

const fieldClass =
  "w-full rounded-lg border-[1.5px] border-tr-line bg-[#FCFFFD] px-3.5 py-3 text-[14.5px] text-ink-900 placeholder:text-slate-400 transition focus:border-brand-primary focus:outline-none focus:ring-[3px] focus:ring-brand-primary/15";

export function ScanForm({ className }: { className?: string }) {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [competitorTags, setCompetitorTags] = useState<string[]>([]);
  const [competitorInput, setCompetitorInput] = useState("");
  const [promptTags, setPromptTags] = useState<string[]>([]);
  const [promptInput, setPromptInput] = useState("");
  const [locale, setLocale] = useState("en-AU");
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  /** Split on commas: completed segments become tags; text after the last comma stays in the input. */
  function onPromptChange(raw: string) {
    if (!raw.includes(",")) {
      setPromptInput(raw);
      return;
    }
    const parts = raw.split(",");
    const completed = parts
      .slice(0, -1)
      .map((s) => s.trim())
      .filter(Boolean);
    const tail = parts[parts.length - 1] ?? "";
    if (completed.length) {
      setPromptTags((prev) => {
        const next = [...prev];
        for (const t of completed) {
          if (next.length >= MAX_PROMPTS) {
            toast.error(`Maximum ${MAX_PROMPTS} prompts`);
            break;
          }
          if (!next.includes(t)) next.push(t);
        }
        return next;
      });
    }
    setPromptInput(tail);
  }

  function onPromptKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      const parts = promptInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      if (!parts.length) return;
      setPromptTags((prev) => {
        const next = [...prev];
        for (const t of parts) {
          if (next.length >= MAX_PROMPTS) {
            toast.error(`Maximum ${MAX_PROMPTS} prompts`);
            break;
          }
          if (!next.includes(t)) next.push(t);
        }
        return next;
      });
      setPromptInput("");
    }
  }

  function onCompetitorChange(raw: string) {
    if (!raw.includes(",")) {
      setCompetitorInput(raw);
      return;
    }
    const parts = raw.split(",");
    const completed = parts
      .slice(0, -1)
      .map((s) => normalizeDomainToken(s))
      .filter(Boolean);
    const tail = parts[parts.length - 1] ?? "";
    if (completed.length) {
      setCompetitorTags((prev) => {
        const next = [...prev];
        for (const t of completed) {
          if (next.length >= MAX_COMPETITORS) {
            toast.error(`Maximum ${MAX_COMPETITORS} competitors`);
            break;
          }
          if (!next.some((x) => domainDedupeKey(x) === domainDedupeKey(t))) next.push(t);
        }
        return next;
      });
    }
    setCompetitorInput(tail);
  }

  function onCompetitorKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      const parts = competitorInput
        .split(",")
        .map((s) => normalizeDomainToken(s))
        .filter(Boolean);
      if (!parts.length) return;
      setCompetitorTags((prev) => {
        const next = [...prev];
        for (const t of parts) {
          if (next.length >= MAX_COMPETITORS) {
            toast.error(`Maximum ${MAX_COMPETITORS} competitors`);
            break;
          }
          if (!next.some((x) => domainDedupeKey(x) === domainDedupeKey(t))) next.push(t);
        }
        return next;
      });
      setCompetitorInput("");
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setLoading(true);
    try {
      let compList = [...competitorTags];
      const compPending = competitorInput
        .split(",")
        .map((s) => normalizeDomainToken(s))
        .filter(Boolean);
      for (const t of compPending) {
        if (compList.length >= MAX_COMPETITORS) {
          toast.error(`Maximum ${MAX_COMPETITORS} competitors`);
          return;
        }
        if (!compList.some((x) => domainDedupeKey(x) === domainDedupeKey(t))) compList.push(t);
      }
      compList = compList.slice(0, MAX_COMPETITORS);

      const mergedPrompts = [...promptTags];
      const pendingParts = promptInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      for (const p of pendingParts) {
        if (mergedPrompts.length >= MAX_PROMPTS) {
          toast.error(`Maximum ${MAX_PROMPTS} prompts`);
          return;
        }
        if (!mergedPrompts.includes(p)) mergedPrompts.push(p);
      }
      setPromptTags(mergedPrompts);
      setPromptInput("");

      const parsed = scanFormSchema.safeParse({
        url,
        competitors: compList,
        prompts: mergedPrompts,
        locale,
      });
      if (!parsed.success) {
        const first = parsed.error.issues[0];
        toast.error(first?.message ?? "Check the form and try again.");
        return;
      }

      const res = await createScan({
        url: parsed.data.url,
        competitors: parsed.data.competitors.length ? parsed.data.competitors : undefined,
        prompts: parsed.data.prompts,
        locale: parsed.data.locale,
      });
      rememberDashboardScan(res.scan_id, parsed.data.url);
      toast.success("Scan started");
      router.push(`/scan/${res.scan_id}`);
    } catch (err: unknown) {
      let msg = "Something went wrong";
      if (err instanceof Error) {
        msg = err.name === "TimeoutError" ? "Request timed out — check the API is reachable." : err.message;
      }
      setSubmitError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={cn("relative", className)}>
      <span className="absolute -top-2.5 right-7 z-10 rounded-md bg-tr-landingOrange px-3 py-1 font-display text-[10px] font-extrabold uppercase tracking-wide text-[#1a1a1a] shadow-sm">
        FREE · 60 SECONDS
      </span>
      <form
        onSubmit={onSubmit}
        className="space-y-4 rounded-[18px] border border-tr-line bg-[#F7FDF9] p-8 shadow-[0_16px_50px_rgba(16,58,38,0.14),0_0_0_1px_#D7EBDD] sm:p-8"
      >
        <div>
          <h3 className="font-display text-lg font-bold text-tr-navy">Run your first citation scan</h3>
          <p className="mt-1 text-[13px] text-tr-mute">
            Paste your website, add competitors if you want, and enter the questions your buyers ask AI.
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="flex items-baseline justify-between font-display text-[12.5px] font-bold tracking-wide text-tr-navy">
              <span>
                Your website <span className="text-red-500">*</span>
              </span>
            </label>
            <input
              type="url"
              className={cn(fieldClass, "mt-1.5")}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://acme.com"
              required
              autoComplete="url"
            />
          </div>

          <div>
            <label className="flex items-baseline justify-between font-display text-[12.5px] font-bold tracking-wide text-tr-navy">
              <span>Competitor domains (optional)</span>
              <span className="text-xs font-medium text-tr-mute">comma-separated or Enter · up to 5</span>
            </label>
            <div
              className={cn(
                "mt-1.5 flex min-h-[52px] flex-wrap items-center gap-1.5 rounded-lg border-[1.5px] border-tr-line bg-[#FCFFFD] px-2.5 py-1 transition focus-within:border-brand-primary focus-within:ring-[3px] focus-within:ring-brand-primary/15",
              )}
            >
              {competitorTags.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1.5 rounded-full border border-brand-primary/35 bg-tr-pale py-1 pl-3 pr-1 font-display text-[13px] font-semibold text-tr-teal"
                >
                  {truncate(t, 36)}
                  <button
                    type="button"
                    className="flex h-4 w-4 items-center justify-center rounded-full bg-tr-teal text-[10px] font-bold leading-none text-white hover:opacity-90"
                    onClick={() => setCompetitorTags((p) => p.filter((x) => x !== t))}
                    aria-label={`Remove ${t}`}
                  >
                    ×
                  </button>
                </span>
              ))}
              <input
                className="min-w-[120px] flex-1 border-0 bg-transparent px-1 py-1.5 text-sm text-ink-900 outline-none placeholder:text-slate-400"
                value={competitorInput}
                onChange={(e) => onCompetitorChange(e.target.value)}
                onKeyDown={onCompetitorKeyDown}
                placeholder="Optional: hubspot.com, salesforce.com…"
              />
            </div>
          </div>

          <div>
            <label className="flex items-baseline justify-between font-display text-[12.5px] font-bold tracking-wide text-tr-navy">
              <span>
                Buyer questions to monitor <span className="text-red-500">*</span>
              </span>
              <span className="text-xs font-medium text-tr-mute">comma-separated or Enter · up to {MAX_PROMPTS}</span>
            </label>
            <div
              className={cn(
                "mt-1.5 flex min-h-[52px] flex-wrap items-center gap-1.5 rounded-lg border-[1.5px] border-tr-line bg-[#FCFFFD] px-2.5 py-1 transition focus-within:border-brand-primary focus-within:ring-[3px] focus-within:ring-brand-primary/15",
              )}
            >
              {promptTags.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1.5 rounded-full border border-brand-primary/35 bg-tr-pale py-1 pl-3 pr-1 font-display text-[13px] font-semibold text-tr-teal"
                >
                  {truncate(t, 40)}
                  <button
                    type="button"
                    className="flex h-4 w-4 items-center justify-center rounded-full bg-tr-teal text-[10px] font-bold leading-none text-white hover:opacity-90"
                    onClick={() => setPromptTags((p) => p.filter((x) => x !== t))}
                    aria-label={`Remove ${t}`}
                  >
                    ×
                  </button>
                </span>
              ))}
              <input
                className="min-w-[120px] flex-1 border-0 bg-transparent px-1 py-1.5 text-sm text-ink-900 outline-none placeholder:text-slate-400"
                value={promptInput}
                onChange={(e) => onPromptChange(e.target.value)}
                onKeyDown={onPromptKeyDown}
                placeholder="e.g. best CRM for SMB, how to choose an agency…"
              />
            </div>
          </div>

          <div>
            <label className="flex items-baseline justify-between font-display text-[12.5px] font-bold tracking-wide text-tr-navy">
              <span>Locale</span>
              <span className="text-xs font-medium text-tr-mute">where buyers are searching</span>
            </label>
            <Select className={cn(fieldClass, "mt-1.5 cursor-pointer")} value={locale} onChange={(e) => setLocale(e.target.value)}>
              <option value="en-AU">🇦🇺 Australia (en-AU)</option>
              <option value="en-US">🇺🇸 United States (en-US)</option>
              <option value="en-GB">🇬🇧 United Kingdom (en-GB)</option>
              <option value="en-IN">🇮🇳 India (en-IN)</option>
              <option value="de-DE">German (de-DE)</option>
              <option value="fr-FR">French (fr-FR)</option>
              <option value="es-ES">Spanish (es-ES)</option>
            </Select>
          </div>
        </div>

        <div className="pt-1">
          <button
            type="submit"
            disabled={loading}
            className="landing-form-submit w-full rounded-[10px] py-3.5 font-display text-[14.5px] font-bold uppercase tracking-[0.07em] text-white transition hover:brightness-[1.03] disabled:pointer-events-none disabled:opacity-50"
          >
            {loading ? "Starting…" : "▶ Start free citation scan"}
          </button>
          {submitError ? (
            <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-center text-[13px] text-red-800">
              {submitError}
              <span className="mt-1 block text-[11.5px] text-red-700/90">
                Tip: set <code className="rounded bg-red-100 px-1">NEXT_PUBLIC_API_URL</code> to your API (same
                browser-reachable URL) and ensure CORS allows this site.
              </span>
            </p>
          ) : (
            <p className="mt-3 text-center text-[11.5px] text-tr-mute">
              No credit card. Live results in <strong className="font-bold text-tr-teal">~60 seconds</strong>.
              We&apos;ll email a permanent link.
            </p>
          )}
        </div>
      </form>
    </div>
  );
}

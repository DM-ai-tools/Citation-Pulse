import { z } from "zod";

/** Bare domain or full URL → canonical https URL for the API. */
export function normalizeWebsiteInput(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) {
    throw new Error("Website is required");
  }
  let candidate = trimmed;
  if (!/^https?:\/\//i.test(candidate)) {
    candidate = `https://${candidate.replace(/^\/+/, "")}`;
  }
  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    throw new Error("Enter a valid website or domain (e.g. hipages.com.au)");
  }
  const host = parsed.hostname;
  if (!host || !host.includes(".")) {
    throw new Error("Enter a valid website or domain (e.g. hipages.com.au)");
  }
  const path =
    parsed.pathname && parsed.pathname !== "/"
      ? parsed.pathname.replace(/\/+$/, "") || "/"
      : "/";
  const search = parsed.search || "";
  return `https://${host}${path === "/" && !search ? "/" : path}${search}`;
}

const websiteField = z
  .string()
  .trim()
  .min(1, "Website is required")
  .transform((s) => normalizeWebsiteInput(s));

export const scanFormSchema = z.object({
  url: websiteField,
  competitors: z
    .array(z.string().trim().min(1))
    .max(5)
    .default([])
    .transform((rows) =>
      rows
        .map((line) => {
          const t = line.trim();
          if (!t) return "";
          try {
            return normalizeWebsiteInput(t);
          } catch {
            return "";
          }
        })
        .filter(Boolean),
    ),
  prompts: z
    .array(z.string().trim().min(1))
    .min(1, "Add at least one prompt")
    .max(8, "Max 8 prompts"),
  locale: z.enum(["en-US", "en-GB", "en-AU", "en-IN", "de-DE", "fr-FR", "es-ES"]).default("en-AU"),
  engines: z.array(z.string()).optional(),
});

export type ScanFormValues = z.infer<typeof scanFormSchema>;

export function parseCompetitorLine(line: string): string {
  const t = line.trim();
  if (!t) return "";
  try {
    return normalizeWebsiteInput(t);
  } catch {
    return t.startsWith("http") ? t : `https://${t}`;
  }
}

/** Split comma- or newline-separated competitor domains (max 5). */
export function parseCompetitorsField(raw: string): string[] {
  const parts = raw
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  return parts.slice(0, 5);
}

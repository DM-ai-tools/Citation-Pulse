import { z } from "zod";

const domainLike = z
  .string()
  .trim()
  .min(1)
  .max(253)
  .regex(/^([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$|^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$/);

export const scanFormSchema = z.object({
  url: z
    .string()
    .trim()
    .min(1, "URL is required")
    .transform((s) => (s.startsWith("http") ? s : `https://${s}`))
    .pipe(z.string().url("Enter a valid URL")),
  competitors: z.array(z.string().trim()).max(5).default([]),
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
  return t.startsWith("http") ? t : `https://${t}`;
}

/** Split comma- or newline-separated competitor domains (max 5). */
export function parseCompetitorsField(raw: string): string[] {
  const parts = raw
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  return parts.slice(0, 5);
}

export const competitorSchema = z.union([z.string().url(), domainLike]);

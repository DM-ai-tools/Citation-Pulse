/** Turn FastAPI / proxy error bodies into a short user-facing message. */
export function formatApiErrorBody(status: number, raw: string): string {
  const text = (raw || "").trim();
  if (!text) {
    if (status === 422) return "Invalid form data — check your website and prompts.";
    if (status === 429) return "Too many scans — wait a moment and try again.";
    if (status >= 500) return "Server error — restart the API (npm run dev:api) and try again.";
    return `Request failed (${status})`;
  }
  try {
    const data = JSON.parse(text) as { detail?: unknown };
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const parts = detail
        .map((row) => {
          if (!row || typeof row !== "object") return "";
          const msg = "msg" in row ? String((row as { msg?: string }).msg || "") : "";
          const loc = "loc" in row && Array.isArray((row as { loc?: unknown }).loc)
            ? (row as { loc: unknown[] }).loc.join(".")
            : "";
          return loc ? `${loc}: ${msg}` : msg;
        })
        .filter(Boolean);
      if (parts.length) return parts.join(" · ");
    }
  } catch {
    /* not JSON */
  }
  if (text.length > 280) return `${text.slice(0, 277)}…`;
  return text;
}

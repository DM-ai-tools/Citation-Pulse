import { CitationPulseMark } from "@/components/shared/BrandMark";
import { TrafficRadiusLogo } from "@/components/shared/TrafficRadiusLogo";
import { cn } from "@/lib/utils";

function rootHost(url: string) {
  try {
    const u = url.startsWith("http") ? url : `https://${url}`;
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return url.replace(/^https?:\/\//, "").split("/")[0] ?? url;
  }
}

export function ScanLiveHeader({
  status,
  url,
}: {
  status: string;
  url: string;
}) {
  const live = status !== "completed";
  const host = rootHost(url);

  return (
    <header className="sticky top-0 z-[100] border-b border-tr-line bg-white shadow-[0_1px_3px_rgba(10,37,64,0.04)]">
      <div className="mx-auto flex h-[76px] max-w-[1280px] flex-wrap items-center justify-between gap-4 px-6">
        <div className="flex items-center gap-3.5">
          <a href="https://trafficradius.com.au/" target="_blank" rel="noopener noreferrer">
            <TrafficRadiusLogo variant="remote" />
          </a>
          <span className="hidden h-[34px] w-px bg-tr-line sm:block" />
          <CitationPulseMark
            tagline={live ? "PROCESSING · LIVE SCAN" : "SCAN COMPLETE"}
            className="hidden sm:block"
          />
        </div>
        <div className="flex flex-wrap items-center gap-4">
          {live && (
            <span
              className={cn(
                "inline-flex items-center gap-2 rounded-full border border-brand-primary px-3.5 py-1.5 font-display text-xs font-bold uppercase tracking-[0.07em] text-tr-teal",
                "bg-gradient-to-r from-brand-primary/10 to-brand-primary/20",
              )}
            >
              <span className="h-2 w-2 animate-landing-pulse rounded-full bg-brand-primary" />
              Live scan in progress
            </span>
          )}
          <span className="text-xs font-medium text-tr-mute">{host}</span>
        </div>
      </div>
    </header>
  );
}

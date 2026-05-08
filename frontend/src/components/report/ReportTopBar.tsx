"use client";

import { Mail, Share2, FileDown } from "lucide-react";
import { CitationPulseMark } from "@/components/shared/BrandMark";
import { TrafficRadiusLogo } from "@/components/shared/TrafficRadiusLogo";

export function ReportTopBar({
  urlHost,
  generatedAt,
  onShare,
  onPdf,
}: {
  urlHost: string;
  generatedAt: string;
  onShare: () => void;
  onPdf: () => void;
}) {
  return (
    <header className="sticky top-0 z-[100] border-b border-tr-line bg-white shadow-[0_1px_3px_rgba(10,37,64,0.04)]">
      <div className="mx-auto flex h-[76px] max-w-[1280px] flex-wrap items-center justify-between gap-4 px-6">
        <div className="flex shrink-0 items-center gap-3.5">
          <a href="https://trafficradius.com.au/" target="_blank" rel="noopener noreferrer">
            <TrafficRadiusLogo variant="remote" />
          </a>
          <span className="hidden h-[34px] w-px bg-tr-line sm:block" />
          <CitationPulseMark tagline="FULL CITATION REPORT" className="hidden sm:block" />
        </div>
        <p className="hidden min-w-0 flex-1 px-4 text-center text-[12.5px] text-tr-mute md:block">
          Report for <strong className="text-tr-navy">{urlHost}</strong>
          <span className="mx-1 text-tr-line">·</span>
          generated <strong className="text-tr-navy">{generatedAt}</strong>
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onPdf}
            className="inline-flex items-center gap-1.5 rounded-lg border-[1.5px] border-tr-line bg-white px-3.5 py-2 font-display text-[12.5px] font-bold text-tr-navy transition hover:border-brand-primary hover:text-brand-primary"
          >
            <FileDown className="h-4 w-4" /> PDF
          </button>
          <button
            type="button"
            onClick={onShare}
            className="inline-flex items-center gap-1.5 rounded-lg border-[1.5px] border-tr-line bg-white px-3.5 py-2 font-display text-[12.5px] font-bold text-tr-navy transition hover:border-brand-primary hover:text-brand-primary"
          >
            <Share2 className="h-4 w-4" /> Share
          </button>
          <button
            type="button"
            onClick={() => {
              const subject = encodeURIComponent(`CitationPulse report: ${urlHost}`);
              window.location.href = `mailto:sales@trafficradius.com.au?subject=${subject}`;
            }}
            className="landing-gradient-cta inline-flex items-center gap-1.5 rounded-lg border border-transparent px-3.5 py-2 font-display text-[12.5px] font-bold text-white transition"
          >
            <Mail className="h-4 w-4" /> Email
          </button>
        </div>
      </div>
    </header>
  );
}

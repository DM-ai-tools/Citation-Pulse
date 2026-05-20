"use client";

import Link from "next/link";
import { FileDown, ArrowRight } from "lucide-react";
import { CitationPulseMark } from "@/components/shared/BrandMark";
import { TrafficRadiusLogo } from "@/components/shared/TrafficRadiusLogo";

export function PublicReportTopBar({ onPdf }: { onPdf?: () => void }) {
  return (
    <div className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-4">
          <a href="https://trafficradius.com.au/" target="_blank" rel="noopener noreferrer">
            <TrafficRadiusLogo />
          </a>
          <span className="hidden h-8 w-px bg-slate-200 sm:block" />
          <CitationPulseMark stamp="Shared Public Report" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onPdf}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-tr-navy hover:bg-slate-50"
          >
            <FileDown className="h-4 w-4" /> Download PDF
          </button>
          <Link
            href="/landing"
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand-primary px-4 py-2 text-xs font-bold uppercase tracking-wide text-white hover:bg-brand-primaryDark"
          >
            Check your own <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </div>
  );
}

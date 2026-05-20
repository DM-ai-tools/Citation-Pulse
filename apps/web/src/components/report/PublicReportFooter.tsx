import Link from "next/link";

export function PublicReportFooter() {
  return (
    <footer className="border-t border-slate-800 bg-tr-navy text-slate-400">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-5 text-xs sm:px-6 lg:px-8">
        <p>
          <span className="font-bold text-white">CitationPulse</span>
          <span className="mx-2 text-slate-500">·</span>
          A Traffic Radius product
        </p>
        <div className="flex flex-wrap items-center gap-5">
          <Link href="/privacy" className="hover:text-white">
            Privacy
          </Link>
          <Link href="/terms" className="hover:text-white">
            Terms
          </Link>
        </div>
        <div>
          <a href="tel:1300852340" className="font-semibold text-white hover:underline">
            1300 852 340
          </a>
          <span className="mx-2 text-slate-500">·</span>
          Melbourne
        </div>
      </div>
    </footer>
  );
}

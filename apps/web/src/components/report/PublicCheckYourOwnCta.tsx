import Link from "next/link";
import { ArrowRight } from "lucide-react";

export function PublicCheckYourOwnCta() {
  return (
    <div className="rounded-2xl bg-gradient-to-br from-tr-navy to-tr-navyDeep p-8 text-center text-white shadow-lift">
      <h3 className="font-display text-xl font-bold leading-snug sm:text-2xl">
        See your own brand&apos;s{" "}
        <span className="text-brand-primaryBright">AI visibility</span> — free.
      </h3>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-slate-300">
        CitationPulse is a Traffic Radius product. Run a free scan in 60 seconds and find out where you&apos;re being
        cited in ChatGPT, Claude, Perplexity, and Gemini.
      </p>
      <div className="mt-5 flex justify-center">
        <Link
          href="/landing"
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand-primary px-6 py-3 text-sm font-bold uppercase tracking-wide text-white shadow-md transition hover:bg-brand-primaryDark"
        >
          Run free scan <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

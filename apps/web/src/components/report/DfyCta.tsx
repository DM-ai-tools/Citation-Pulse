import Link from "next/link";

export function DfyCta() {
  return (
    <div className="rounded-[18px] bg-gradient-to-br from-tr-navy from-0% to-tr-navy2 to-100% px-7 py-7 text-center text-white shadow-[0_12px_30px_rgba(10,37,64,0.18)]">
      <h4 className="font-display text-[19px] font-black leading-snug">
        Want us to <span className="text-brand-primaryBright">grow your AI citations</span> for you?
      </h4>
      <p className="mx-auto mt-2 max-w-lg text-[13px] leading-relaxed text-white/85">
        Traffic Radius DFY operators run citation-building campaigns end to end — outreach, content, source seeding —
        with SLA timers.
      </p>
      <div className="mt-3.5 flex flex-wrap justify-center gap-2 text-[11.5px]">
        <span className="rounded-full border border-brand-primary/30 bg-white/[0.06] px-3 py-1.5">SLA timers</span>
        <span className="rounded-full border border-brand-primary/30 bg-white/[0.06] px-3 py-1.5">Operator console</span>
        <span className="rounded-full border border-brand-primary/30 bg-white/[0.06] px-3 py-1.5">Weekly reviews</span>
      </div>
      <div className="mt-4">
        <Link
          href="/dashboard"
          className="landing-gradient-cta inline-flex items-center justify-center rounded-lg px-5 py-3 font-display text-[13px] font-extrabold uppercase tracking-wide text-white"
        >
          Open dashboard →
        </Link>
      </div>
    </div>
  );
}

import Link from "next/link";
import { Container } from "./Container";

export function MarketingFooter() {
  return (
    <>
      <section className="bg-gradient-to-br from-tr-navy from-0% to-tr-navy2 to-100% px-6 py-[60px] text-white lg:px-8">
        <Container>
          <div className="flex max-w-[1180px] flex-wrap items-center justify-between gap-8">
            <h2 className="max-w-[700px] font-display text-[26px] font-black leading-tight tracking-[-0.8px] sm:text-[30px]">
              See where your brand stands inside{" "}
              <span className="text-brand-primaryBright">
                ChatGPT, Claude, Perplexity, and Gemini
              </span>{" "}
              — in 60 seconds.
            </h2>
            <Link
              href="/landing#top"
              className="landing-gradient-cta shrink-0 rounded-lg px-8 py-4 font-display text-[14.5px] font-bold uppercase tracking-wide text-white transition"
            >
              Run free scan →
            </Link>
          </div>
        </Container>
      </section>
      <footer className="bg-tr-navy px-6 py-9 text-[13px] text-[#B3C7BC] lg:px-8">
        <Container>
          <div className="flex max-w-[1180px] flex-wrap items-center justify-between gap-4">
            <p className="font-display font-extrabold text-white">
              Citation<span className="text-brand-primary">Pulse</span> · A Traffic Radius product
            </p>
            <div className="flex flex-wrap gap-4">
              <Link href="/privacy" className="opacity-70 transition hover:text-white hover:opacity-100">
                Privacy
              </Link>
              <Link href="/terms" className="opacity-70 transition hover:text-white hover:opacity-100">
                Terms
              </Link>
            </div>
            <div>
              <a href="tel:1300852340" className="font-semibold text-white hover:underline">
                1300 852 340
              </a>
              <span className="mx-2 text-white/40">·</span>
              Melbourne
            </div>
          </div>
        </Container>
      </footer>
    </>
  );
}

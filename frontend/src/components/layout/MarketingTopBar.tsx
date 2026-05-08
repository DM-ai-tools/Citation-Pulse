import { Container } from "./Container";

export function MarketingTopBar() {
  return (
    <div className="bg-tr-navy py-1.5 text-[12.5px] text-white">
      <Container className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-white/95">
          📍 Melbourne · Australia · Free for businesses with under 100 monitored prompts
        </span>
        <div className="inline-flex items-center gap-2 font-semibold text-white/95">
          <span className="h-1.5 w-1.5 rounded-full bg-brand-primary" aria-hidden />
          <a href="mailto:info@trafficradius.com.au" className="hover:text-white">
            info@trafficradius.com.au
          </a>
          <span className="text-white/60">•</span>
          <a href="tel:1300852340" className="hover:text-white">
            1300 852 340
          </a>
        </div>
      </Container>
    </div>
  );
}

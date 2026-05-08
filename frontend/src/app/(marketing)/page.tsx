import Link from "next/link";
import { ScanForm } from "@/components/marketing/ScanForm";
import { Container } from "@/components/layout/Container";

const engineCards = [
  { name: "ChatGPT", meta: "OpenAI Responses API", dot: "green" as const },
  { name: "Claude", meta: "Anthropic Messages API", dot: "green" as const },
  { name: "Perplexity", meta: "Sonar API", dot: "green" as const },
  { name: "Gemini", meta: "Google AI Studio", dot: "green" as const },
];

const features = [
  {
    icon: "📊",
    title: "Share of Voice score",
    body: 'Single number that says "are we winning?" — brand citations as a share of you + competitors, per engine, per week.',
  },
  {
    icon: "🔍",
    title: "Citation explorer",
    body: "Filterable table of every URL the AI cited as a source, with engine, prompt, snippet, position, and ownership classification.",
  },
  {
    icon: "🎯",
    title: "Prioritised gap list",
    body: "Prompts where competitors are cited and you aren't, graded A/B/C by estimated search volume and engine coverage.",
  },
  {
    icon: "🔔",
    title: "Slack & email alerts",
    body: "Configurable rules — SoV drops, lost citations, new competitor mentions, sentiment turning negative — fire to your channels.",
  },
  {
    icon: "📄",
    title: "Weekly PDF digest",
    body: "Auto-generated summary every Monday morning with trend lines, top wins and the top three gaps to action this week.",
  },
  {
    icon: "🤝",
    title: "Done-For-You operations",
    body: "Hand the gap list to Traffic Radius. Our operators run citation-building campaigns — outreach, content, source seeding — with SLA timers.",
  },
];

export default function LandingPage() {
  return (
    <>
      <section id="top" className="landing-hero-bg relative overflow-hidden px-6 pb-[90px] pt-[70px] lg:px-8">
        <Container>
          <div className="grid max-w-[1180px] gap-14 lg:grid-cols-[1.1fr_1fr] lg:items-center lg:gap-14">
            <div>
              <div className="mb-6 inline-flex items-center gap-2.5 rounded-full border border-brand-primary bg-white px-4 py-1.5 font-display text-xs font-bold uppercase tracking-wide text-tr-teal shadow-[0_2px_10px_rgba(34,184,209,0.12)]">
                <span className="h-2 w-2 animate-landing-pulse rounded-full bg-brand-primary" aria-hidden />
                NEW · TRACKS 4 AI ENGINES
              </div>
              <h1 className="font-display text-[2.5rem] font-black leading-[1.08] tracking-[-1.5px] text-tr-navy sm:text-[3rem] lg:text-[54px]">
                Are you cited when AI <span className="text-brand-primary">answers buyers&apos;</span> questions?
              </h1>
              <span className="landing-under-mark block" aria-hidden />
              <p className="max-w-[540px] text-[17px] leading-relaxed text-tr-body">
                CitationPulse fires your most important buyer questions at ChatGPT, Claude, Perplexity, and Gemini
                every day — then shows you exactly where your brand is being mentioned, where competitors are winning,
                and which gaps to close first.
              </p>
              <div className="mt-8 flex flex-wrap gap-7">
                {[
                  ["4", "AI ENGINES MONITORED"],
                  ["~50", "PROMPTS PER BRAND"],
                  ["250", "DAILY CITATION CHECKS"],
                  ["24h", "FIRST-INSIGHT SLA"],
                ].map(([n, l]) => (
                  <div key={l}>
                    <p className="font-display text-[28px] font-black leading-none text-tr-navy">{n}</p>
                    <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-tr-mute">{l}</p>
                  </div>
                ))}
              </div>
            </div>
            <ScanForm />
          </div>
        </Container>
      </section>

      <section id="how" className="scroll-mt-28 bg-[#F3FBF6] px-6 py-[70px] lg:px-8">
        <Container>
          <div className="max-w-[1180px]">
            <p className="mb-3 text-xs font-extrabold uppercase tracking-[1.4px] text-brand-primary">How it works</p>
            <h2 className="max-w-[760px] font-display text-[32px] font-black leading-[1.15] tracking-[-1px] text-tr-navy sm:text-[38px]">
              Three steps. <span className="text-brand-primary">One unified scoreboard</span> for AI visibility.
            </h2>
            <p className="mt-3 max-w-[720px] text-base leading-relaxed text-tr-body">
              CitationPulse turns the open question — &quot;are buyers being told about us when they ask AI?&quot; — into
              a daily, measurable answer with a clear to-do list of the gaps to close first.
            </p>
            <div className="mt-8 grid gap-6 md:grid-cols-3">
              {[
                {
                  n: "01",
                  icon: "📝",
                  t: "Tell us about your brand",
                  d: "Add your domains, competitors, and the questions buyers really ask. We auto-suggest 30+ candidate prompts from your site to get you started.",
                },
                {
                  n: "02",
                  icon: "⚡",
                  t: "We poll all major AI engines",
                  d: "Every day, a worker fires each prompt at ChatGPT, Claude, Perplexity, and Gemini. Every cited URL is captured and classified.",
                },
                {
                  n: "03",
                  icon: "📈",
                  t: "You see the scoreboard",
                  d: "Dashboard shows Share of Voice vs. competitors, prompt × engine matrix, and a prioritised gap list — graded A/B/C by opportunity size.",
                },
              ].map((s) => (
                <div
                  key={s.n}
                  className="relative rounded-[14px] border border-tr-line bg-[#FCFFFD] px-[26px] pb-[30px] pt-[30px]"
                >
                  <span className="pointer-events-none font-display text-[60px] font-black leading-none tracking-[-2px] text-tr-pale">
                    {s.n}
                  </span>
                  <span className="absolute right-7 top-7 flex h-11 w-11 items-center justify-center rounded-full bg-tr-pale text-xl text-tr-teal">
                    {s.icon}
                  </span>
                  <h3 className="font-display text-[19px] font-extrabold text-tr-navy">{s.t}</h3>
                  <p className="mt-2.5 text-[14.5px] leading-relaxed text-tr-body">{s.d}</p>
                </div>
              ))}
            </div>
          </div>
        </Container>
      </section>

      <section id="engines" className="scroll-mt-28 bg-[#F1FAF5] px-6 py-[70px] lg:px-8">
        <Container>
          <div className="max-w-[1180px]">
            <p className="mb-3 text-xs font-extrabold uppercase tracking-[1.4px] text-brand-primary">AI Engines we monitor</p>
            <h2 className="font-display text-[32px] font-black leading-[1.15] tracking-[-1px] text-tr-navy sm:text-[38px]">
              Every major engine. <span className="text-brand-primary">Real citations.</span> Daily.
            </h2>
            <p className="mt-3 max-w-[720px] text-base leading-relaxed text-tr-body">
              We monitor ChatGPT, Claude, Perplexity, and Gemini through direct API integrations and capture citations
              from every response.
            </p>
            <div className="mt-5 grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
              {engineCards.map((e) => (
                <div
                  key={e.name}
                  className="rounded-[14px] border-[1.5px] border-tr-line bg-[#FCFFFD] px-[18px] py-6 text-center transition hover:-translate-y-0.5 hover:border-brand-primary"
                >
                  <p className="font-display text-[15px] font-extrabold text-tr-navy">{e.name}</p>
                  <p className="mt-1 text-[11.5px] font-semibold text-tr-mute">
                    <span
                      className={`mr-1.5 inline-block h-2 w-2 rounded-full align-middle ${
                        e.dot === "green" ? "bg-emerald-500" : "bg-tr-landingOrange"
                      }`}
                    />
                    {e.meta}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </Container>
      </section>

      <section id="features" className="scroll-mt-28 bg-[#F6FCF8] px-6 py-[70px] lg:px-8">
        <Container>
          <div className="max-w-[1180px]">
            <p className="mb-3 text-xs font-extrabold uppercase tracking-[1.4px] text-brand-primary">What you get</p>
            <h2 className="max-w-[760px] font-display text-[32px] font-black leading-[1.15] tracking-[-1px] text-tr-navy sm:text-[38px]">
              The <span className="text-brand-primary">scoreboard</span> · the matrix · the to-do list.
            </h2>
            <div className="mt-10 grid gap-[22px] md:grid-cols-2">
              {features.map((f) => (
                <div
                  key={f.title}
                  className="flex gap-[18px] rounded-[14px] border border-tr-line bg-[#FCFFFD] p-[26px]"
                >
                  <div className="flex h-[46px] w-[46px] shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-primary to-tr-teal text-[22px] text-white shadow-sm">
                    {f.icon}
                  </div>
                  <div className="min-w-0">
                    <h4 className="font-display text-[17px] font-extrabold text-tr-navy">{f.title}</h4>
                    <p className="mt-1.5 text-sm leading-relaxed text-tr-body">{f.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Container>
      </section>
    </>
  );
}

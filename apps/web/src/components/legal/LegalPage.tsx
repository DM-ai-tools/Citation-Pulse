import Link from "next/link";
import { Container } from "@/components/layout/Container";

export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: React.ReactNode;
}) {
  return (
    <Container className="max-w-3xl py-12 lg:py-16">
      <p className="text-xs font-semibold uppercase tracking-wide text-brand-primary">Citation Pulse</p>
      <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-tr-navy sm:text-4xl">{title}</h1>
      <p className="mt-2 text-sm text-tr-mute">Last updated {updated}</p>
      <div className="mt-10 space-y-8 text-[15px] leading-relaxed text-tr-body">{children}</div>
      <p className="mt-12 border-t border-tr-line pt-8 text-sm text-tr-mute">
        <Link href="/landing" className="font-semibold text-brand-primary hover:underline">
          ← Back to Citation Pulse
        </Link>
      </p>
    </Container>
  );
}

export function LegalSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="font-display text-lg font-bold text-tr-navy">{title}</h2>
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}

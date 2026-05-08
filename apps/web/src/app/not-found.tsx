import Link from "next/link";

export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center p-8">
      <div className="space-y-4 text-center">
        <h1 className="text-2xl font-bold text-ink-900">Page not found</h1>
        <Link href="/" className="font-medium text-brand-primary hover:underline">
          Back to home
        </Link>
      </div>
    </main>
  );
}

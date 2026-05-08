import type { Metadata } from "next";
import { ClientToaster } from "./client-toaster";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "CitationPulse",
  description: "GEO citation monitoring",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
        <ClientToaster />
      </body>
    </html>
  );
}

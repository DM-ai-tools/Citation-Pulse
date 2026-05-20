"use client";

import { Card } from "@/components/primitives";

export default function AdminAnalyticsPage() {
  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl font-bold text-tr-navy">Analytics</h1>
      <Card className="border-tr-line p-6 text-sm text-tr-mute">
        Engine usage distribution, citation trends, and top scanned domains will appear here as scan
        volume grows. Use the Dashboard and Reports sections for live counts today.
      </Card>
    </div>
  );
}

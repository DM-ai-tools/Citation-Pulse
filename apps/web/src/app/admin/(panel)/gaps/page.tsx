"use client";

import { Card } from "@/components/primitives";

export default function AdminGapsPage() {
  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl font-bold text-tr-navy">Gap analysis overview</h1>
      <Card className="border-tr-line p-6 text-sm text-tr-mute">
        Aggregate gap grades, competitor citation frequency, and coverage statistics across all brands
        will be summarized here. Per-brand gaps remain available in each workspace.
      </Card>
    </div>
  );
}

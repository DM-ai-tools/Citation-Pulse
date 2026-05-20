"use client";

import { Card } from "@/components/primitives";

export default function AdminSettingsPage() {
  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl font-bold text-tr-navy">Settings</h1>
      <Card className="space-y-4 border-tr-line p-6 text-sm text-tr-mute">
        <p>System settings (API keys, scan limits, competitor expansion caps) are stored in the database.</p>
        <p>
          Configure provider keys via environment variables on the API service. Use{" "}
          <code className="rounded bg-slate-100 px-1 font-mono text-xs">PUT /api/v1/admin/settings/{"{key}"}</code>{" "}
          for runtime toggles when the admin API is extended.
        </p>
      </Card>
    </div>
  );
}

-- Tiered competitor discovery persisted on funnel scans (filled when scan completes).
ALTER TABLE scans ADD COLUMN IF NOT EXISTS discovery_params JSONB NULL;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS competitor_discovery JSONB NULL;

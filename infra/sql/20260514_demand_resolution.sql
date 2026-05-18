-- Top Gap Opportunities — demand resolution columns on prompts.
-- Stores the resolved demand signal so the nightly scorer never re-fetches at request time.
-- Safe to re-run: every statement is IF NOT EXISTS.

ALTER TABLE prompts
  ADD COLUMN IF NOT EXISTS demand_score numeric(5,4) NULL,
  ADD COLUMN IF NOT EXISTS demand_bucket text NULL,
  ADD COLUMN IF NOT EXISTS demand_source text NULL,
  ADD COLUMN IF NOT EXISTS demand_variant text NULL,
  ADD COLUMN IF NOT EXISTS demand_raw_volume integer NULL,
  ADD COLUMN IF NOT EXISTS demand_refreshed_at timestamptz NULL;

-- ``demand_bucket`` must be one of: high | medium | low | unknown.
-- We use a soft check (CHECK NOT VALID lets old rows keep NULL) and a CASE-insensitive guard at the app layer.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ck_prompts_demand_bucket'
  ) THEN
    ALTER TABLE prompts
      ADD CONSTRAINT ck_prompts_demand_bucket
      CHECK (demand_bucket IS NULL OR demand_bucket IN ('high','medium','low','unknown'));
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ck_prompts_demand_source'
  ) THEN
    ALTER TABLE prompts
      ADD CONSTRAINT ck_prompts_demand_source
      CHECK (demand_source IS NULL OR demand_source IN ('literal','variant','internal','default'));
  END IF;
END $$;

-- Speeds up the weekly ``refresh_demand`` task: "prompts older than 7 days".
CREATE INDEX IF NOT EXISTS ix_prompts_demand_refreshed_at
  ON prompts (demand_refreshed_at NULLS FIRST);

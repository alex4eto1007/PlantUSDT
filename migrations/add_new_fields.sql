-- Add new fields from recent updates
ALTER TABLE users ADD COLUMN IF NOT EXISTS interstitial_ads_disabled BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS interstitial_disabled_at TIMESTAMP NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS has_received_welcome_bonus BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS welcome_bonus_claimed_at TIMESTAMP NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tasks_completed INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_task_completed_at TIMESTAMP NULL;

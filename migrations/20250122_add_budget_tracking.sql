-- Add user budgets table for budget tracking and alerts
-- Migration: Create user_budgets table

CREATE TABLE IF NOT EXISTS va_user_budgets (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  monthly_budget_cents INTEGER NOT NULL DEFAULT 5000, -- $50 default budget
  alert_thresholds INTEGER[] DEFAULT ARRAY[80, 90, 100], -- Alert at 80%, 90%, 100%
  last_alert_sent_at TIMESTAMP WITH TIME ZONE,
  last_alert_threshold INTEGER,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  UNIQUE(user_id)
);

-- Add index for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_budgets_user_id ON va_user_budgets(user_id);
CREATE INDEX IF NOT EXISTS idx_user_budgets_active ON va_user_budgets(is_active) WHERE is_active = true;

-- Add trigger to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_va_user_budgets_updated_at BEFORE UPDATE
  ON va_user_budgets FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- Add comments
COMMENT ON TABLE va_user_budgets IS 'User budget settings and alert thresholds for cost management';
COMMENT ON COLUMN va_user_budgets.monthly_budget_cents IS 'Monthly budget in cents (e.g., 5000 = $50)';
COMMENT ON COLUMN va_user_budgets.alert_thresholds IS 'Array of percentage thresholds to trigger alerts (e.g., [80, 90, 100])';
COMMENT ON COLUMN va_user_budgets.last_alert_sent_at IS 'Timestamp of last budget alert sent to prevent spam';
COMMENT ON COLUMN va_user_budgets.last_alert_threshold IS 'The threshold percentage that triggered the last alert';

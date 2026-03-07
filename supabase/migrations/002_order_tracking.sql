-- Order Tracking Enhancement
-- Adds dedicated columns for industry, personas, and Apple order number

ALTER TABLE orders ADD COLUMN IF NOT EXISTS industry TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS personas TEXT[] DEFAULT '{}';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS apple_order_number TEXT;

-- Best-effort migration of existing data from notes field
UPDATE orders
SET
  industry = TRIM(SPLIT_PART(SPLIT_PART(notes, 'Industry: ', 2), ',', 1)),
  personas = string_to_array(
    TRIM(SPLIT_PART(notes, 'Personas: ', 2)),
    ', '
  )
WHERE notes LIKE 'Industry:%'
  AND industry IS NULL;

-- Index for quick lookups by industry or Apple order number
CREATE INDEX IF NOT EXISTS idx_orders_industry ON orders (industry);
CREATE INDEX IF NOT EXISTS idx_orders_apple_order_number ON orders (apple_order_number);

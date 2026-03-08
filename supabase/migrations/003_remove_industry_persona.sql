-- Remove Industry/Persona System
-- All 12 tool suites are now loaded on every commissioned Mac.
-- Industry and persona columns are no longer needed.

-- Drop index added in 002
DROP INDEX IF EXISTS idx_orders_industry;

-- Drop columns from orders (added in 002)
ALTER TABLE orders DROP COLUMN IF EXISTS industry;
ALTER TABLE orders DROP COLUMN IF EXISTS personas;

-- Drop industry from profiles (added in 001)
ALTER TABLE profiles DROP COLUMN IF EXISTS industry;

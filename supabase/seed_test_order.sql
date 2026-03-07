-- Test order for device CLI provisioning
-- Run this in Supabase SQL Editor after migrations are applied.
-- Requires at least one row in profiles (sign up once in the app, or create a user in Auth).
--
-- Order ID (use this in job.txt or when the setup script asks):  a1b2c3d4-e5f6-4789-a012-3456789abcde
-- Serial number for device:                                     H0N9QH6W4K

INSERT INTO orders (
  id,
  client_id,
  status,
  hardware_type,
  hardware_config,
  software_package,
  total_price_hkd,
  notes
)
SELECT
  'a1b2c3d4-e5f6-4789-a012-3456789abcde'::uuid,
  p.id,
  'paid'::order_status,
  'mac_mini_m4'::hardware_type,
  '{}'::jsonb,
  'base',
  50000,
  'Test order for device CLI – serial H0N9QH6W4K'
FROM profiles p
LIMIT 1;

-- If the insert fails with "no row from LIMIT 1", create a user in Supabase Auth first so a profile exists.

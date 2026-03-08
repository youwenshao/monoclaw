-- Seed test orders for device CLI provisioning
-- Run this in Supabase SQL Editor after all migrations (001–003) are applied.
-- Requires at least one row in profiles (sign up once in the app, or create a user in Auth).
--
-- Order A (Barebones / API-only):  a1b2c3d4-e5f6-4789-a012-3456789abcde  serial H0N9QH6W4K
-- Order B (Pro Bundle / Qwen):     b2c3d4e5-f6a7-4890-b123-456789abcdef  serial J1P0RK7X5L
-- Order C (Max Bundle):            c3d4e5f6-a7b8-4901-c234-56789abcdef0  serial K2Q1SL8Y6M

-- ============================================================
-- Remove existing barebones seed order (Order A) so we can re-insert
-- in the current schema. Cascades handle order_addons and order_status_history;
-- devices and their test data must be deleted first (no CASCADE on order_id).
-- ============================================================
DELETE FROM device_test_results
WHERE device_id IN (SELECT id FROM devices WHERE order_id = 'a1b2c3d4-e5f6-4789-a012-3456789abcde'::uuid);
DELETE FROM device_test_summaries
WHERE device_id IN (SELECT id FROM devices WHERE order_id = 'a1b2c3d4-e5f6-4789-a012-3456789abcde'::uuid);
DELETE FROM devices WHERE order_id = 'a1b2c3d4-e5f6-4789-a012-3456789abcde'::uuid;
DELETE FROM orders WHERE id = 'a1b2c3d4-e5f6-4789-a012-3456789abcde'::uuid;

-- ============================================================
-- ORDER A: Barebones (API-only, no local models)
-- Mac mini M4, base software only, HK$39,999
-- ============================================================
INSERT INTO orders (id, client_id, status, hardware_type, hardware_config, software_package, total_price_hkd, notes)
SELECT
  'a1b2c3d4-e5f6-4789-a012-3456789abcde'::uuid,
  p.id,
  'paid'::order_status,
  'mac_mini_m4'::hardware_type,
  '{}'::jsonb,
  'base',
  39999,
  'Seed order A – Barebones API-only, serial H0N9QH6W4K'
FROM profiles p
LIMIT 1;

INSERT INTO order_status_history (order_id, from_status, to_status, notes)
VALUES (
  'a1b2c3d4-e5f6-4789-a012-3456789abcde'::uuid,
  'pending_payment'::order_status,
  'paid'::order_status,
  'Seed: payment confirmed'
);

-- ============================================================
-- ORDER B: Pro Bundle with Qwen-family models
-- Mac mini M4, base + Pro Bundle (HK$999), HK$40,998
-- Models: qwen-3.5-0.8b (fast), qwen-3.5-9b (think), qwen-2.5-coder-7b (coder)
-- ============================================================
INSERT INTO orders (id, client_id, status, hardware_type, hardware_config, software_package, total_price_hkd, notes)
SELECT
  'b2c3d4e5-f6a7-4890-b123-456789abcdef'::uuid,
  p.id,
  'paid'::order_status,
  'mac_mini_m4'::hardware_type,
  '{}'::jsonb,
  'base',
  40998,
  'Seed order B – Pro Bundle (Qwen family), serial J1P0RK7X5L'
FROM profiles p
LIMIT 1;

INSERT INTO order_addons (order_id, addon_type, addon_name, category, price_hkd) VALUES
  ('b2c3d4e5-f6a7-4890-b123-456789abcdef'::uuid, 'bundle', 'pro_bundle', 'pro_bundle'::addon_category, 999),
  ('b2c3d4e5-f6a7-4890-b123-456789abcdef'::uuid, 'model',  'qwen-3.5-0.8b',      'fast'::addon_category,       99),
  ('b2c3d4e5-f6a7-4890-b123-456789abcdef'::uuid, 'model',  'qwen-3.5-9b',         'think'::addon_category,     599),
  ('b2c3d4e5-f6a7-4890-b123-456789abcdef'::uuid, 'model',  'qwen-2.5-coder-7b',   'coder'::addon_category,     399);

INSERT INTO order_status_history (order_id, from_status, to_status, notes)
VALUES (
  'b2c3d4e5-f6a7-4890-b123-456789abcdef'::uuid,
  'pending_payment'::order_status,
  'paid'::order_status,
  'Seed: payment confirmed'
);

-- ============================================================
-- ORDER C: Max Bundle (all 16 models + auto-routing)
-- iMac M4, base + Max Bundle (HK$1,999), HK$51,998
-- ============================================================
INSERT INTO orders (id, client_id, status, hardware_type, hardware_config, software_package, total_price_hkd, notes)
SELECT
  'c3d4e5f6-a7b8-4901-c234-56789abcdef0'::uuid,
  p.id,
  'paid'::order_status,
  'imac_m4'::hardware_type,
  '{"color": "Silver"}'::jsonb,
  'base',
  51998,
  'Seed order C – Max Bundle, serial K2Q1SL8Y6M'
FROM profiles p
LIMIT 1;

INSERT INTO order_addons (order_id, addon_type, addon_name, category, price_hkd) VALUES
  ('c3d4e5f6-a7b8-4901-c234-56789abcdef0'::uuid, 'bundle', 'max_bundle', 'max_bundle'::addon_category, 1999);

INSERT INTO order_status_history (order_id, from_status, to_status, notes)
VALUES (
  'c3d4e5f6-a7b8-4901-c234-56789abcdef0'::uuid,
  'pending_payment'::order_status,
  'paid'::order_status,
  'Seed: payment confirmed'
);

-- If inserts fail with "no row from LIMIT 1", create a user in Supabase Auth first so a profile exists.

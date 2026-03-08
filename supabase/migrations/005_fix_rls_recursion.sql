-- Fix infinite recursion in RLS: "Admins can manage all profiles" on profiles
-- queried profiles itself. This migration adds a SECURITY DEFINER helper and
-- updates all admin policies to use it (for DBs that already ran 001 and 004).

CREATE OR REPLACE FUNCTION public.is_admin_or_technician()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND role IN ('admin', 'technician')
  );
$$;

-- Profiles: drop self-referential policy and recreate using helper
DROP POLICY IF EXISTS "Admins can manage all profiles" ON profiles;
CREATE POLICY "Admins can manage all profiles"
  ON profiles FOR ALL
  USING (public.is_admin_or_technician());

-- Orders
DROP POLICY IF EXISTS "Admins can manage all orders" ON orders;
CREATE POLICY "Admins can manage all orders"
  ON orders FOR ALL
  USING (public.is_admin_or_technician());

-- Order addons
DROP POLICY IF EXISTS "Admins can manage all order addons" ON order_addons;
CREATE POLICY "Admins can manage all order addons"
  ON order_addons FOR ALL
  USING (public.is_admin_or_technician());

-- Order status history
DROP POLICY IF EXISTS "Admins can manage all order history" ON order_status_history;
CREATE POLICY "Admins can manage all order history"
  ON order_status_history FOR ALL
  USING (public.is_admin_or_technician());

-- Devices
DROP POLICY IF EXISTS "Admins can manage all devices" ON devices;
CREATE POLICY "Admins can manage all devices"
  ON devices FOR ALL
  USING (public.is_admin_or_technician());

-- Device test results
DROP POLICY IF EXISTS "Admins can manage all test results" ON device_test_results;
CREATE POLICY "Admins can manage all test results"
  ON device_test_results FOR ALL
  USING (public.is_admin_or_technician());

-- Device test summaries
DROP POLICY IF EXISTS "Admins can manage all test summaries" ON device_test_summaries;
CREATE POLICY "Admins can manage all test summaries"
  ON device_test_summaries FOR ALL
  USING (public.is_admin_or_technician());

-- Signing system (004) – only if tables exist
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'signing_sessions') THEN
    DROP POLICY IF EXISTS "Admins can manage all signing sessions" ON signing_sessions;
    CREATE POLICY "Admins can manage all signing sessions"
      ON signing_sessions FOR ALL
      USING (public.is_admin_or_technician());
  END IF;
  IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'audit_trail') THEN
    DROP POLICY IF EXISTS "Admins can view all audit entries" ON audit_trail;
    CREATE POLICY "Admins can view all audit entries"
      ON audit_trail FOR SELECT
      USING (public.is_admin_or_technician());
  END IF;
  IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'contract_templates') THEN
    DROP POLICY IF EXISTS "Admins can manage templates" ON contract_templates;
    CREATE POLICY "Admins can manage templates"
      ON contract_templates FOR ALL
      USING (public.is_admin_or_technician());
  END IF;
END $$;

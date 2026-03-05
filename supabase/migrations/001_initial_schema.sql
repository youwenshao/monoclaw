-- MonoClaw Initial Schema
-- Supabase (PostgreSQL) migration

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE order_status AS ENUM (
  'pending_payment',
  'paid',
  'hardware_pending',
  'hardware_received',
  'provisioning',
  'testing',
  'ready',
  'shipped',
  'delivered',
  'completed'
);

CREATE TYPE hardware_type AS ENUM ('mac_mini_m4', 'imac_m4');

CREATE TYPE addon_category AS ENUM (
  'fast', 'standard', 'think', 'coder',
  'pro_bundle', 'max_bundle'
);

CREATE TYPE device_setup_status AS ENUM (
  'registered', 'provisioning', 'testing', 'passed', 'failed', 'shipped'
);

CREATE TYPE test_status AS ENUM ('pass', 'fail', 'warning', 'skipped');

CREATE TYPE test_category AS ENUM (
  'hardware',
  'macos_environment',
  'openclaw_core',
  'llm_models',
  'voice_system',
  'security',
  'stress_edge_cases'
);

-- ============================================================
-- TABLES
-- ============================================================

CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'client' CHECK (role IN ('client', 'admin', 'technician')),
  company_name TEXT,
  industry TEXT,
  contact_name TEXT,
  contact_phone TEXT,
  language_pref TEXT DEFAULT 'en' CHECK (language_pref IN ('en', 'zh-hant', 'zh-hans')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  client_id UUID NOT NULL REFERENCES profiles(id),
  status order_status NOT NULL DEFAULT 'pending_payment',
  hardware_type hardware_type NOT NULL,
  hardware_config JSONB DEFAULT '{}',
  software_package TEXT NOT NULL DEFAULT 'base',
  total_price_hkd INTEGER NOT NULL,
  stripe_payment_intent_id TEXT,
  stripe_checkout_session_id TEXT,
  delivery_address TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE order_addons (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  addon_type TEXT NOT NULL CHECK (addon_type IN ('model', 'bundle')),
  addon_name TEXT NOT NULL,
  category addon_category NOT NULL,
  price_hkd INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE order_status_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  from_status order_status,
  to_status order_status NOT NULL,
  notes TEXT,
  updated_by UUID REFERENCES profiles(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE devices (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  order_id UUID NOT NULL REFERENCES orders(id),
  serial_number TEXT,
  hardware_type hardware_type NOT NULL,
  mac_address TEXT,
  setup_status device_setup_status NOT NULL DEFAULT 'registered',
  technician_id UUID REFERENCES profiles(id),
  setup_started_at TIMESTAMPTZ,
  setup_completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE device_test_results (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  category test_category NOT NULL,
  test_name TEXT NOT NULL,
  status test_status NOT NULL,
  details JSONB DEFAULT '{}',
  duration_ms INTEGER,
  executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE device_test_summaries (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  total_tests INTEGER NOT NULL DEFAULT 0,
  passed INTEGER NOT NULL DEFAULT 0,
  failed INTEGER NOT NULL DEFAULT 0,
  warnings INTEGER NOT NULL DEFAULT 0,
  skipped INTEGER NOT NULL DEFAULT 0,
  overall_status test_status NOT NULL,
  full_report_json JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_orders_client_id ON orders(client_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_order_addons_order_id ON order_addons(order_id);
CREATE INDEX idx_order_status_history_order_id ON order_status_history(order_id);
CREATE INDEX idx_devices_order_id ON devices(order_id);
CREATE INDEX idx_devices_setup_status ON devices(setup_status);
CREATE INDEX idx_device_test_results_device_id ON device_test_results(device_id);
CREATE INDEX idx_device_test_results_category ON device_test_results(category);
CREATE INDEX idx_device_test_summaries_device_id ON device_test_summaries(device_id);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_addons ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_test_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_test_summaries ENABLE ROW LEVEL SECURITY;

-- Profiles policies
CREATE POLICY "Users can view own profile"
  ON profiles FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
  ON profiles FOR UPDATE
  USING (auth.uid() = id);

CREATE POLICY "Admins can manage all profiles"
  ON profiles FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('admin', 'technician')
    )
  );

-- Orders policies
CREATE POLICY "Clients can view own orders"
  ON orders FOR SELECT
  USING (client_id = auth.uid());

CREATE POLICY "Clients can insert own orders"
  ON orders FOR INSERT
  WITH CHECK (client_id = auth.uid());

CREATE POLICY "Admins can manage all orders"
  ON orders FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('admin', 'technician')
    )
  );

-- Order addons policies
CREATE POLICY "Clients can view own order addons"
  ON order_addons FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM orders
      WHERE orders.id = order_addons.order_id AND orders.client_id = auth.uid()
    )
  );

CREATE POLICY "Clients can insert own order addons"
  ON order_addons FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM orders
      WHERE orders.id = order_addons.order_id AND orders.client_id = auth.uid()
    )
  );

CREATE POLICY "Admins can manage all order addons"
  ON order_addons FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('admin', 'technician')
    )
  );

-- Order status history policies
CREATE POLICY "Clients can view own order history"
  ON order_status_history FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM orders
      WHERE orders.id = order_status_history.order_id AND orders.client_id = auth.uid()
    )
  );

CREATE POLICY "Admins can manage all order history"
  ON order_status_history FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('admin', 'technician')
    )
  );

-- Devices policies
CREATE POLICY "Clients can view own devices"
  ON devices FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM orders
      WHERE orders.id = devices.order_id AND orders.client_id = auth.uid()
    )
  );

CREATE POLICY "Admins can manage all devices"
  ON devices FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('admin', 'technician')
    )
  );

-- Device test results policies
CREATE POLICY "Clients can view own device test results"
  ON device_test_results FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM devices
      JOIN orders ON orders.id = devices.order_id
      WHERE devices.id = device_test_results.device_id AND orders.client_id = auth.uid()
    )
  );

CREATE POLICY "Admins can manage all test results"
  ON device_test_results FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('admin', 'technician')
    )
  );

-- Device test summaries policies
CREATE POLICY "Clients can view own device test summaries"
  ON device_test_summaries FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM devices
      JOIN orders ON orders.id = devices.order_id
      WHERE devices.id = device_test_summaries.device_id AND orders.client_id = auth.uid()
    )
  );

CREATE POLICY "Admins can manage all test summaries"
  ON device_test_summaries FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('admin', 'technician')
    )
  );

-- ============================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================

-- Auto-create profile on user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, contact_name, role)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data ->> 'full_name', NEW.raw_user_meta_data ->> 'name', ''),
    'client'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER orders_updated_at
  BEFORE UPDATE ON orders
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER devices_updated_at
  BEFORE UPDATE ON devices
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER profiles_updated_at
  BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

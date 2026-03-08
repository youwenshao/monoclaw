-- Native Signing System (NSS) Schema
-- Adds contract signing with audit trail, email verification, and PDF evidence

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE client_type AS ENUM ('individual', 'entity');

CREATE TYPE signing_status AS ENUM (
  'pending_email',
  'pending_signature',
  'completed',
  'expired'
);

CREATE TYPE audit_event_type AS ENUM (
  'email_sent',
  'email_verified',
  'contract_viewed',
  'checkbox_toggled',
  'signature_submitted',
  'pdf_generated',
  'email_delivered'
);

-- ============================================================
-- TABLES
-- ============================================================

CREATE TABLE signing_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  client_type client_type NOT NULL,
  legal_name TEXT NOT NULL,
  entity_jurisdiction TEXT,
  br_number TEXT,
  representative_name TEXT,
  representative_title TEXT,
  email TEXT NOT NULL,
  email_verified_at TIMESTAMPTZ,
  verification_code_hash TEXT,
  verification_expires_at TIMESTAMPTZ,
  verification_attempts INTEGER NOT NULL DEFAULT 0,
  ip_address INET,
  user_agent TEXT,
  template_version TEXT,
  agreement_checks JSONB DEFAULT '[]'::jsonb,
  signature_font_text TEXT,
  signed_at TIMESTAMPTZ,
  status signing_status NOT NULL DEFAULT 'pending_email',
  immutable_pdf_path TEXT,
  audit_chain_hash TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_trail (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES signing_sessions(id),
  event_type audit_event_type NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ip_address INET,
  user_agent TEXT,
  metadata JSONB,
  previous_hash TEXT,
  current_hash TEXT
);

CREATE TABLE contract_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version TEXT NOT NULL UNIQUE,
  html_content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_active BOOLEAN NOT NULL DEFAULT FALSE
);

-- Link orders to signing sessions
ALTER TABLE orders ADD COLUMN signing_session_id UUID REFERENCES signing_sessions(id);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_signing_sessions_user_id ON signing_sessions(user_id);
CREATE INDEX idx_signing_sessions_status ON signing_sessions(status);
CREATE INDEX idx_signing_sessions_email ON signing_sessions(email);
CREATE INDEX idx_audit_trail_session_id ON audit_trail(session_id);
CREATE INDEX idx_audit_trail_event_type ON audit_trail(event_type);
CREATE INDEX idx_audit_trail_timestamp ON audit_trail(timestamp);
CREATE INDEX idx_contract_templates_active ON contract_templates(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_orders_signing_session_id ON orders(signing_session_id);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE signing_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_trail ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_templates ENABLE ROW LEVEL SECURITY;

-- Signing sessions: users can view/insert their own
CREATE POLICY "Users can view own signing sessions"
  ON signing_sessions FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own signing sessions"
  ON signing_sessions FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own signing sessions"
  ON signing_sessions FOR UPDATE
  USING (user_id = auth.uid());

CREATE POLICY "Admins can manage all signing sessions"
  ON signing_sessions FOR ALL
  USING (public.is_admin_or_technician());

-- Audit trail: append-only for authenticated users, admins can also read
CREATE POLICY "Authenticated users can insert audit entries"
  ON audit_trail FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM signing_sessions
      WHERE signing_sessions.id = audit_trail.session_id
        AND signing_sessions.user_id = auth.uid()
    )
  );

CREATE POLICY "Admins can view all audit entries"
  ON audit_trail FOR SELECT
  USING (public.is_admin_or_technician());

-- Contract templates: readable by all authenticated, writable by admins
CREATE POLICY "Authenticated users can view active templates"
  ON contract_templates FOR SELECT
  USING (auth.uid() IS NOT NULL);

CREATE POLICY "Admins can manage templates"
  ON contract_templates FOR ALL
  USING (public.is_admin_or_technician());

-- ============================================================
-- HASH CHAIN TRIGGER (tamper-evident audit trail)
-- ============================================================

CREATE OR REPLACE FUNCTION calculate_audit_hash()
RETURNS TRIGGER AS $$
DECLARE
  prev_hash TEXT;
  content TEXT;
BEGIN
  SELECT current_hash INTO prev_hash
  FROM audit_trail
  WHERE session_id = NEW.session_id
  ORDER BY timestamp DESC
  LIMIT 1;

  IF prev_hash IS NULL THEN
    prev_hash := 'genesis';
  END IF;

  NEW.previous_hash := prev_hash;

  content := COALESCE(NEW.session_id::text, '')
    || COALESCE(NEW.event_type::text, '')
    || COALESCE(NEW.timestamp::text, '')
    || COALESCE(NEW.ip_address::text, '')
    || COALESCE(NEW.user_agent, '')
    || COALESCE(NEW.metadata::text, '');

  NEW.current_hash := encode(
    digest(content || prev_hash, 'sha256'),
    'hex'
  );

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_trail_hash_chain
  BEFORE INSERT ON audit_trail
  FOR EACH ROW EXECUTE FUNCTION calculate_audit_hash();

-- ============================================================
-- UPDATED_AT TRIGGER FOR SIGNING SESSIONS
-- ============================================================

CREATE TRIGGER signing_sessions_updated_at
  BEFORE UPDATE ON signing_sessions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- STORAGE: Signed contracts bucket with WORM-style protection
-- ============================================================

-- Create the storage bucket (private, no public access)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'signed-contracts',
  'signed-contracts',
  FALSE,
  10485760, -- 10MB limit
  ARRAY['application/pdf']
)
ON CONFLICT (id) DO NOTHING;

-- Allow service role to upload (handled by service client in API routes)
-- Prevent deletion of signed contracts by anyone except service role
CREATE POLICY "Prevent PDF deletion by non-service-role"
  ON storage.objects FOR DELETE
  USING (bucket_id != 'signed-contracts');

-- Allow authenticated users to read their own signed contracts
CREATE POLICY "Users can read own signed contracts"
  ON storage.objects FOR SELECT
  USING (
    bucket_id = 'signed-contracts'
    AND auth.uid() IS NOT NULL
    AND (
      EXISTS (
        SELECT 1 FROM signing_sessions
        WHERE signing_sessions.user_id = auth.uid()
          AND storage.objects.name LIKE 'contracts/' || signing_sessions.id::text || '/%'
      )
      OR EXISTS (
        SELECT 1 FROM profiles
        WHERE id = auth.uid() AND role IN ('admin', 'technician')
      )
    )
  );

-- ============================================================
-- SEED: Initial contract template (v1.0)
-- ============================================================

INSERT INTO contract_templates (version, html_content, is_active) VALUES (
  'v1.0',
  E'<div class="contract">\n'
  '<h1>Service Agreement</h1>\n'
  '<p>This Service Agreement (&ldquo;Agreement&rdquo;) is entered into as of <strong>{{signed_date}}</strong> by and between:</p>\n'
  '<p><strong>Sentimento Technologies Limited</strong>, a company incorporated in Hong Kong (&ldquo;Service Provider&rdquo;, &ldquo;Bailee&rdquo;, &ldquo;Agent&rdquo;, &ldquo;Data Processor&rdquo;); and</p>\n'
  '{{#if_individual}}\n'
  '<p><strong>{{legal_name}}</strong> (&ldquo;Client&rdquo;, &ldquo;Bailor&rdquo;, &ldquo;Principal&rdquo;, &ldquo;Data Subject&rdquo;).</p>\n'
  '{{/if_individual}}\n'
  '{{#if_entity}}\n'
  '<p><strong>{{legal_name}}</strong>, incorporated in <strong>{{entity_jurisdiction}}</strong> with company registration number <strong>{{br_number}}</strong> (&ldquo;Client&rdquo;, &ldquo;Bailor&rdquo;, &ldquo;Principal&rdquo;, &ldquo;Data Subject&rdquo;).</p>\n'
  '{{/if_entity}}\n'
  '\n'
  '<h2>1. Scope of Services</h2>\n'
  '<p>The Service Provider agrees to provide the Client with the MonoClaw AI Employee system, including hardware provisioning, software installation, and ongoing support as described in the order configuration.</p>\n'
  '\n'
  '<h2>2. Hardware Bailment</h2>\n'
  '<p>The Client acknowledges that the hardware device (&ldquo;Mac&rdquo;) is purchased by the Client from Apple and delivered to the Service Provider for the sole purpose of software installation, configuration, and testing. The Service Provider shall exercise reasonable care in handling the hardware during the provisioning period.</p>\n'
  '\n'
  '<h2>3. Software License</h2>\n'
  '<p>The Service Provider grants the Client a non-exclusive, non-transferable license to use the OpenClaw software suite and all included tool suites on the provisioned device. This license is perpetual and tied to the specific hardware device.</p>\n'
  '\n'
  '<h2>4. Data Processing</h2>\n'
  '<p>The Service Provider will process personal data only as necessary for provisioning and support. All AI processing occurs locally on the Client&rsquo;s device after delivery. The Service Provider complies with the Personal Data (Privacy) Ordinance (Cap. 486).</p>\n'
  '\n'
  '<h2>5. Payment Terms</h2>\n'
  '<p>The Client agrees to pay the total amount as specified in the order configuration. Payment is processed via Stripe in Hong Kong Dollars (HKD). All payments are non-refundable once hardware provisioning has commenced.</p>\n'
  '\n'
  '<h2>6. Delivery &amp; Acceptance</h2>\n'
  '<p>The Service Provider will deliver the provisioned device to the Client&rsquo;s specified address. The Client must confirm receipt within 7 days of delivery. Failure to confirm receipt within 14 days constitutes deemed acceptance.</p>\n'
  '\n'
  '<h2>7. Warranty &amp; Support</h2>\n'
  '<p>The Service Provider warrants that the software will perform substantially as described for a period of 90 days from delivery. Hardware warranty is provided directly by Apple under their standard terms.</p>\n'
  '\n'
  '<h2>8. Limitation of Liability</h2>\n'
  '<p>The Service Provider&rsquo;s total liability under this Agreement shall not exceed the total amount paid by the Client. The Service Provider shall not be liable for indirect, consequential, or incidental damages.</p>\n'
  '\n'
  '<h2>9. Governing Law</h2>\n'
  '<p>This Agreement shall be governed by and construed in accordance with the laws of the Hong Kong Special Administrative Region. Any disputes shall be subject to the exclusive jurisdiction of the courts of Hong Kong.</p>\n'
  '\n'
  '<h2>10. Electronic Signature</h2>\n'
  '<p>The parties agree that this Agreement may be executed by electronic signature in accordance with the Electronic Transactions Ordinance (Cap. 553) of the Laws of Hong Kong. Each party acknowledges that their electronic signature shall have the same legal effect as a handwritten signature.</p>\n'
  '\n'
  '<div class="signature-block">\n'
  '<h3>SERVICE PROVIDER:</h3>\n'
  '<p>Name: Sentimento Technologies Limited</p>\n'
  '<p>Authorized Representative: _______________</p>\n'
  '<p>Title: Director</p>\n'
  '\n'
  '<h3>CLIENT:</h3>\n'
  '{{#if_individual}}\n'
  '<p>Name: {{legal_name}}</p>\n'
  '<p>Signature: <span class="signature-font">{{legal_name}}</span></p>\n'
  '{{/if_individual}}\n'
  '{{#if_entity}}\n'
  '<p>Name: {{legal_name}}</p>\n'
  '<p>Signature: <span class="signature-font">{{representative_name}}</span></p>\n'
  '<p>Title: {{representative_title}}</p>\n'
  '{{/if_entity}}\n'
  '<p>Date: {{signed_date}}</p>\n'
  '<p>Contract ID: {{contract_id}}</p>\n'
  '</div>\n'
  '</div>',
  TRUE
);

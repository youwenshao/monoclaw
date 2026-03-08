# Native Signing System (NSS)

The Native Signing System (NSS) is the contract-signing pipeline used by Sentimento Technologies Limited before Stripe payment. It provides legally enforceable, auditable e-signatures under the Electronic Transactions Ordinance (Cap. 553) of Hong Kong.

## Flow Overview

1. **Review** → User must be signed in (Google OAuth). Order config is preserved in `localStorage` across sign-in.
2. **Continue to Contract** → NSS starts.
3. **Stage 0–1**: Choose **Individual** or **Corporate** client; capture identity (name, email; for entities: jurisdiction, BR number, representative name/title).
4. **Stage 2**: 6-digit verification code sent via **Resend**; user enters code (max 3 attempts, 15‑minute expiry).
5. **Stage 3**: Contract rendered from active template; three mandatory checkboxes; 10‑second minimum review timer; each checkbox toggle is logged to the audit trail.
6. **Stage 4**: Signature preview (script font); user types name exactly to confirm; submit signs the contract.
7. **Post-sign**: PDF generated (pdf-lib), stored in Supabase Storage (`signed-contracts`), and emailed to the client (with optional BCC). User returns to Review and clicks **Pay** → Stripe.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RESEND_API_KEY` | Yes | Resend API key for verification and contract emails. |
| `RESEND_FROM_EMAIL` | No | Sender (default: `Native Signing System <contracts@sentimento.tech>`). Must be a verified domain in Resend. |
| `ADMIN_EMAIL` | No | BCC for “Contract Executed” emails (default: `team@sentimento.dev`). |

## Database (Supabase)

- **`signing_sessions`**: Per-user signing session (client type, identity, email verification state, signature, status, PDF path). RLS: user sees own rows; admins see all.
- **`audit_trail`**: Append-only log of events (`email_sent`, `email_verified`, `contract_viewed`, `checkbox_toggled`, `signature_submitted`, `pdf_generated`, `email_delivered`) with IP, user agent, and hash chain. RLS: insert for session owner; admins can select.
- **`contract_templates`**: Versioned HTML templates (`version`, `html_content`, `is_active`). Version is locked on the session when the user enters the contract review step.

Migration: `supabase/migrations/004_signing_system.sql` (enums, tables, RLS, hash-chain trigger, storage bucket).

## API Routes

All under `app/api/signing/`:

- `POST create-session` — Create session (auth required); validates identity and BR number for entities.
- `POST send-verification` — Generate 6-digit code, store hash, send via Resend; logs `email_sent`.
- `POST verify-code` — Verify code, set `email_verified_at`, status `pending_signature`; logs `email_verified`. Rate limit: 3 attempts.
- `POST log-event` — Append audit entry (e.g. `contract_viewed`, `checkbox_toggled`). Hash chain is maintained by DB trigger.
- `POST submit-signature` — Validate checkboxes and name match; set `signed_at`, status `completed`; triggers async `generate-pdf`.
- `POST generate-pdf` — Build PDF (pdf-lib), upload to `signed-contracts`, send contract email via Resend; logs `pdf_generated`, `email_delivered`.

## Security & Compliance

- **Rate limiting**: Max 3 verification attempts per session.
- **Hash chain**: Each `audit_trail` row has `previous_hash` and `current_hash` (SHA-256) for tamper-evident history.
- **Template version lock**: Session stores `template_version` at review start so the user always completes the version they saw.
- **WORM-style storage**: `signed-contracts` bucket policies prevent deletion of signed PDFs.
- **IP and User-Agent**: Captured on session creation and on each audit event.

## Key Files

- **Frontend**: `app/[locale]/(checkout)/order/contract/` (identity, verify, review, sign steps); `order/review/review-step.tsx` (auth gate and “Continue to Contract” / “Pay”).
- **State**: `lib/checkout-context.tsx` (`signingSessionId`, `setSigningSession`, `signingComplete`).
- **Backend**: `lib/signing.ts` (validation, constants), `lib/resend.ts` (Resend), `lib/pdf-generator.ts` (PDF from template).

This is the MonoClaw **web app**: Next.js marketing site, order configuration, contract signing (Native Signing System), and Stripe checkout. Operated by Sentimento Technologies Limited.

## Getting Started

### Environment

Copy `.env.local.example` to `.env.local` and fill in:

- **Supabase**: URL, anon key, and service role key. For **Google SSO**, see **[docs/AUTH_GOOGLE_SSO.md](docs/AUTH_GOOGLE_SSO.md)**.
- **Stripe**: Publishable key, secret key, and webhook secret for checkout.
- **Resend**: API key for NSS verification emails and signed-contract delivery. Optional: `RESEND_FROM_EMAIL`, `ADMIN_EMAIL` (BCC for contract emails).

See **[docs/NATIVE_SIGNING_SYSTEM.md](docs/NATIVE_SIGNING_SYSTEM.md)** for NSS flow and environment details.

### Run the dev server

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser.

### Checkout & Native Signing System (NSS)

The order flow is **guest-friendly** until contract and payment:

1. **Hardware** → **Add-ons** → **Tools** → **Review** (order summary).
2. At Review, users must **sign in** (Google OAuth). Order state is kept in `localStorage` across sign-in.
3. **Contract** (NSS): client type (Individual/Entity) → identity capture → email verification (6-digit code via Resend) → contract review (10s timer + 3 checkboxes) → signature (type-to-confirm).
4. After signing, user returns to Review and clicks **Pay** → Stripe Checkout → confirmation. Signed PDF is generated (pdf-lib), stored in Supabase Storage, and emailed via Resend.

Key code: `lib/checkout-context.tsx` (order + `signingSessionId`), `app/[locale]/(checkout)/order/*`, `app/api/signing/*`, `lib/resend.ts`, `lib/pdf-generator.ts`.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

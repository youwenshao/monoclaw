# Google SSO (Supabase Auth)

The web app uses **Supabase Auth** with **Google OAuth** for sign-in. This doc covers one-time setup and common failures so we don’t run into the same issues again.

---

## How it works

1. User clicks “Sign in with Google” → app calls `signInWithOAuth({ provider: "google" })` with `redirectTo: ${origin}/auth/callback`.
2. Supabase redirects the user to **Google** with `redirect_uri` = **Supabase’s** callback URL (not the app’s).
3. User signs in on Google; Google redirects back to **Supabase** with an authorization code.
4. Supabase exchanges that code for tokens with Google, then redirects the user to the app’s `/auth/callback`.
5. The app’s callback route exchanges the code for a session and redirects to the dashboard.

So **Google only sees Supabase’s callback URL**. Your app’s `redirectTo` is used only by Supabase after the exchange.

---

## One-time setup

### 1. Google Cloud Console (OAuth client)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**.
2. Create or select a **Web application** OAuth 2.0 Client ID (not Desktop, Android, or iOS).
3. **Authorized redirect URIs** — add **exactly**:
   ```text
   https://<YOUR_SUPABASE_PROJECT_REF>.supabase.co/auth/v1/callback
   ```
   Get the project ref from your Supabase URL (e.g. `https://abcdefgh.supabase.co` → ref is `abcdefgh`).
4. **Authorized JavaScript origins** — add the origins where the app runs (no trailing slash):
   - Local: `http://localhost:3000` (or your dev port)
   - Production: `https://yourdomain.com`
5. Save. Changes can take a few minutes to apply.

### 2. Supabase Dashboard (Google provider)

1. **Authentication** → **Providers** → **Google** → enable.
2. Paste **Client ID** and **Client secret** from the **same** Web application OAuth client (Google Cloud Console).
3. Save.

### 3. Supabase URL configuration

1. **Authentication** → **URL Configuration**.
2. **Site URL**: your app’s main URL (e.g. `http://localhost:3000` or `https://yourdomain.com`).
3. **Redirect URLs**: add:
   - `http://localhost:3000/auth/callback`
   - `https://yourdomain.com/auth/callback` (for production)

### 4. OAuth consent screen (if app is in Testing)

- **APIs & Services** → **OAuth consent screen** → add the Google accounts that need to sign in as **Test users**, or publish the app.

---

## Troubleshooting

### “You can’t sign in because this app sent an invalid request”

Google is rejecting the request before redirecting back. Usually:

| Cause | Fix |
|--------|-----|
| **Redirect URI mismatch** | In Google Cloud Console, add exactly `https://<project-ref>.supabase.co/auth/v1/callback` to **Authorized redirect URIs**. |
| **Wrong origins** | Add your app origin(s) to **Authorized JavaScript origins** (e.g. `http://localhost:3000`, `https://yourdomain.com`). |
| **Wrong client type** | Use a **Web application** OAuth client, not Desktop/Android/iOS. |

### Callback returns `error=server_error` / `unexpected_failure` / “Unable to exchange external code”

The redirect and code from Google are fine; **Supabase fails when exchanging the code** with Google. Usually:

| Cause | Fix |
|--------|-----|
| **Wrong or mismatched credentials in Supabase** | In Supabase → Authentication → Providers → Google, ensure **Client ID** and **Client secret** are from the **same** Web application OAuth client. Re-copy both from Google Cloud Console; if you regenerated the secret, update Supabase. |
| **Extra spaces when pasting** | Re-paste Client ID and Client secret in Supabase (no leading/trailing spaces). |
| **Google provider disabled** | In Supabase, ensure the Google provider is **enabled**. |

---

## Checklist for new environments

When setting up a new Supabase project or a new deployment origin:

- [ ] Google Cloud: OAuth client type = **Web application**
- [ ] Google Cloud: **Authorized redirect URIs** includes `https://<project-ref>.supabase.co/auth/v1/callback`
- [ ] Google Cloud: **Authorized JavaScript origins** includes the app origin(s)
- [ ] Supabase: **Authentication → Providers → Google** enabled, Client ID and Secret from the same Web client
- [ ] Supabase: **URL Configuration** — Site URL and Redirect URLs include the app URL and `/auth/callback`
- [ ] If consent screen is in Testing: test users added, or app published

---

## Related code

- Sign-in: `web/src/app/[locale]/(client)/auth/sign-in/sign-in-form.tsx` — `signInWithOAuth({ provider: "google", options: { redirectTo: `${origin}/auth/callback` } })`
- Callback: `web/src/app/auth/callback/route.ts` — exchanges code for session and redirects

Env: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (see `web/.env.local.example`).

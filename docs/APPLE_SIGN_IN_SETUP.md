# Sign in with Apple — deployment setup

The Apple OAuth flow is implemented in NEXA. It remains disabled until the Apple Developer configuration and server environment variables below are supplied.

## 1. Apple Developer configuration

1. In Apple Developer, enable **Sign in with Apple** for the App ID used by the service.
2. Create a **Services ID** for the web sign-in client and enable Sign in with Apple for it.
3. Configure the web domain used by the API and add this exact Return URL:

   `https://YOUR_API_DOMAIN/api/v1/auth/oauth/apple/callback`

   Replace `YOUR_API_DOMAIN` with the real HTTPS API hostname. The hostname and URL must match the deployment exactly.
4. Create an Apple Sign in with Apple private key. Keep the downloaded `.p8` file private.

## 2. Generate the Apple client-secret JWT

The backend expects an Apple client-secret JWT, not the raw `.p8` private key. Generate it using:

- Header: `alg=ES256`, `kid=YOUR_KEY_ID`
- Claims: `iss=YOUR_TEAM_ID`, `iat=current_unix_time`, `exp=expiry_unix_time`, `aud=https://appleid.apple.com`, `sub=YOUR_SERVICES_ID`

Use a short operational rotation window (Apple permits a maximum validity of six months). Sign the JWT with the private key. Never commit the private key or generated JWT to Git.

## 3. Configure NEXA server environment

Set these variables in the production API host's secret/environment settings:

- `OAUTH_APPLE_CLIENT_ID` — the Services ID (the JWT `sub` must match).
- `OAUTH_APPLE_CLIENT_SECRET` — the generated ES256 client-secret JWT.
- `AUTH_PUBLIC_BASE_URL` — the public frontend origin used for the post-login redirect, if it differs from the API base URL.

The API must be reachable over HTTPS. Keep the session cookie secure. If the frontend and API are cross-site, configure the session cookie as `SameSite=None; Secure`; if they are same-site, `Lax` is generally appropriate. Also ensure the frontend origin is included in `CORS_ALLOWED_ORIGINS`.

## 4. Verify after deployment

1. Open `GET /api/v1/auth/providers` and confirm the Apple provider reports `enabled: true`.
2. Start Apple sign-in from the NEXA login screen.
3. Complete the Apple consent flow and confirm the browser receives the HttpOnly `nexa_session` cookie.
4. Confirm the app loads the signed-in user via `GET /api/v1/auth/me`.
5. Test both a first-time Apple account (name may only be supplied on first consent) and a returning account.

## Important

Code and CI success do not prove that Apple sign-in works against a live Apple Developer account. A real end-to-end test is required after the credentials, domain, and deployment are configured. Do not send the `.p8` file, client-secret JWT, or other secrets in chat or commit them to this repository.

# WebAuthn / Passkeys — current status

## What exists

| Step | Status |
|------|--------|
| Registration options (`passkey_register_options`) | Implemented — challenge stored 5 min, bound to `user_id`, RP id/name from settings |
| Registration verify (`passkey_register_verify`) | **Partial** — checks challenge ownership/expiry and uniqueness of `credential_id`; stores credential on the user record. Does **not** fully verify WebAuthn attestation/cryptographic public-key binding against the authenticator response. |
| Login options / verify | **Disabled** — explicitly raises `PasskeyError`. UI provider card reports `enabled: false`. |

Password login and OAuth are unaffected.

## Why login is disabled

Without server-side assertion signature verification (origin, RP ID hash, challenge binding, counter, credential public key), accepting a client-supplied `credential_id` would allow forgeable “login”. NEXA refuses that path rather than simulating success.

## Required for a full implementation

1. Dependency such as `webauthn` (or equivalent) for registration attestation + assertion verification.
2. Persist COSE public key + sign count from registration.
3. On login: issue challenge → verify assertion against stored public key, origin, RP ID, and challenge; reject replays.
4. Align `AUTH_RP_ID` / origins with production HTTPS host.
5. Enable the `passkey` provider card only after verification ships.

## Operator note

Do not advertise passkey login in production until the above is complete.

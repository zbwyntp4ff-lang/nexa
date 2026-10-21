/** Browser WebAuthn helpers (passkey create / get). */

function b64urlToBuffer(value: string): ArrayBuffer {
  const pad = "=".repeat((4 - (value.length % 4)) % 4);
  const b64 = (value + pad).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes.buffer;
}

function bufferToB64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let s = "";
  for (let i = 0; i < bytes.length; i += 1) s += String.fromCharCode(bytes[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function webauthnSupported(): boolean {
  return typeof window !== "undefined" && !!window.PublicKeyCredential;
}

export async function passkeyGet(options: {
  challenge: string;
  rpId: string;
  timeout?: number;
  userVerification?: string;
  allowCredentials?: { type: string; id: string }[];
}): Promise<{ credential_id: string; client_data_json: string }> {
  const publicKey: PublicKeyCredentialRequestOptions = {
    challenge: b64urlToBuffer(options.challenge),
    rpId: options.rpId,
    timeout: options.timeout ?? 120_000,
    userVerification: (options.userVerification as UserVerificationRequirement) || "preferred",
    allowCredentials:
      options.allowCredentials && options.allowCredentials.length
        ? options.allowCredentials.map((c) => ({
            type: "public-key" as const,
            id: b64urlToBuffer(c.id),
          }))
        : undefined,
  };
  const cred = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential | null;
  if (!cred) throw new Error("Passkey cancelled");
  const response = cred.response as AuthenticatorAssertionResponse;
  return {
    credential_id: bufferToB64url(cred.rawId),
    client_data_json: bufferToB64url(response.clientDataJSON),
  };
}

export async function passkeyCreate(options: PublicKeyCredentialCreationOptions): Promise<{
  credential_id: string;
  client_data_json: string;
}> {
  const challenge =
    typeof options.challenge === "string"
      ? b64urlToBuffer(options.challenge as unknown as string)
      : options.challenge;
  const userId =
    typeof options.user.id === "string"
      ? b64urlToBuffer(options.user.id as unknown as string)
      : options.user.id;
  const publicKey: PublicKeyCredentialCreationOptions = {
    ...options,
    challenge,
    user: { ...options.user, id: userId },
    excludeCredentials: (options.excludeCredentials || []).map((c) => ({
      ...c,
      id: typeof c.id === "string" ? b64urlToBuffer(c.id as unknown as string) : c.id,
    })),
  };
  const cred = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential | null;
  if (!cred) throw new Error("Passkey cancelled");
  const response = cred.response as AuthenticatorAttestationResponse;
  return {
    credential_id: bufferToB64url(cred.rawId),
    client_data_json: bufferToB64url(response.clientDataJSON),
  };
}

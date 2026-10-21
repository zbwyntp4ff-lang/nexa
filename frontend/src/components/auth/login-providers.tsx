"use client";
import * as React from "react";
import { Apple, KeyRound, Loader2, QrCode } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  fetchAuthProviders,
  passkeyLoginOptions,
  passkeyLoginVerify,
  pollDeviceLogin,
  startDeviceLogin,
  startOAuth,
  type DeviceStartResult,
  type OAuthProviderId,
  type ProvidersResult,
} from "@/lib/auth-api";
import { useT } from "@/lib/i18n";
import { setSessionToken } from "@/lib/session-token";
import { passkeyGet, webauthnSupported } from "@/lib/webauthn";
import { useAuthStore } from "@/store/auth-store";

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="currentColor"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="currentColor"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="currentColor"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.009-.868-.014-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.523 2 12 2z" />
    </svg>
  );
}

export function LoginProviders() {
  const t = useT();
  const bootstrap = useAuthStore((s) => s.bootstrap);
  const [providers, setProviders] = React.useState<ProvidersResult | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [device, setDevice] = React.useState<DeviceStartResult | null>(null);
  const [showDevice, setShowDevice] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    void fetchAuthProviders()
      .then((p) => {
        if (!cancelled) setProviders(p);
      })
      .catch(() => {
        if (!cancelled) setProviders(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    if (!device) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const result = await pollDeviceLogin(device.device_code);
        if (!cancelled) {
          setSessionToken(result.session_token);
          setBusy(null);
          await bootstrap();
        }
      } catch (err) {
        const code = err instanceof ApiError ? err.code : "";
        if (code === "authorization_pending" || code === "DeviceLoginPendingError") {
          return;
        }
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
          setBusy(null);
        }
      }
    };
    const id = window.setInterval(() => void tick(), (device.interval || 2) * 1000);
    void tick();
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [device, bootstrap, t]);

  async function onOAuth(provider: OAuthProviderId) {
    setError(null);
    setBusy(provider);
    try {
      const { authorize_url } = await startOAuth(provider);
      window.location.href = authorize_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
      setBusy(null);
    }
  }

  async function onPasskey() {
    if (!webauthnSupported()) {
      setError(t("auth.passkeyUnsupported"));
      return;
    }
    setError(null);
    setBusy("passkey");
    try {
      const options = await passkeyLoginOptions();
      const assertion = await passkeyGet(options);
      const result = await passkeyLoginVerify(assertion);
      setSessionToken(result.session_token);
      await bootstrap();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.passkeyFailed"));
    } finally {
      setBusy(null);
    }
  }

  async function onDevice() {
    setError(null);
    setBusy("device");
    setShowDevice(true);
    try {
      const started = await startDeviceLogin();
      setDevice(started);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
      setBusy(null);
      setShowDevice(false);
    }
  }

  const oauthEnabled = (id: OAuthProviderId) =>
    providers?.oauth.find((p) => p.id === id)?.enabled ?? false;

  const qrSrc = !device?.qr_svg && device
    ? `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(device.qr_payload)}`
    : null;

  return (
    <div className="space-y-3">
      <div className="relative flex items-center gap-3 py-1">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {t("auth.orContinueWith")}
        </span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Button
          type="button"
          variant="outline"
          className="h-10 w-full gap-2"
          disabled={busy !== null || !oauthEnabled("google")}
          title={!oauthEnabled("google") ? t("auth.providerNotConfigured") : undefined}
          onClick={() => void onOAuth("google")}
        >
          {busy === "google" ? <Loader2 className="size-4 animate-spin" /> : <GoogleIcon className="size-4" />}
          Google
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-10 w-full gap-2"
          disabled={busy !== null || !oauthEnabled("github")}
          title={!oauthEnabled("github") ? t("auth.providerNotConfigured") : undefined}
          onClick={() => void onOAuth("github")}
        >
          {busy === "github" ? <Loader2 className="size-4 animate-spin" /> : <GitHubIcon className="size-4" />}
          GitHub
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-10 w-full gap-2"
          disabled={busy !== null || !oauthEnabled("apple")}
          title={!oauthEnabled("apple") ? t("auth.providerNotConfigured") : undefined}
          onClick={() => void onOAuth("apple")}
        >
          {busy === "apple" ? <Loader2 className="size-4 animate-spin" /> : <Apple className="size-4" />}
          Apple
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Button
          type="button"
          variant="outline"
          className="h-10 w-full gap-2"
          disabled={busy !== null}
          onClick={() => void onPasskey()}
        >
          {busy === "passkey" ? <Loader2 className="size-4 animate-spin" /> : <KeyRound className="size-4" />}
          {t("auth.passkey")}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-10 w-full gap-2"
          disabled={busy !== null && busy !== "device"}
          onClick={() => void onDevice()}
        >
          {busy === "device" && !device ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <QrCode className="size-4" />
          )}
          {t("auth.qrCode")}
        </Button>
      </div>

      {showDevice && device && (
        <div className="rounded-xl border border-border bg-muted/30 p-4 text-center">
          <p className="text-sm text-muted-foreground">{t("auth.deviceHint")}</p>
          <p className="mt-3 font-mono text-2xl font-semibold tracking-[0.2em]">{device.user_code}</p>
          {device.qr_svg ? (
            <div
              className="mx-auto mt-4 w-64 rounded-lg border border-border bg-white p-3 text-black"
              dangerouslySetInnerHTML={{ __html: device.qr_svg }}
            />
          ) : qrSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={qrSrc}
              alt={t("auth.qrCode")}
              width={200}
              height={200}
              className="mx-auto mt-4 rounded-lg border border-border bg-white p-2"
            />
          ) : null}
          {device.phone_url ? (
            <p className="mt-3 break-all text-xs text-foreground">
              {t("auth.devicePhoneUrl")}
              <br />
              <a href={device.phone_url} className="text-primary underline-offset-4 hover:underline" target="_blank" rel="noreferrer">
                {device.phone_url}
              </a>
            </p>
          ) : (
            <p className="mt-3 text-xs text-destructive">{t("auth.deviceNoLan")}</p>
          )}
          <Button
            type="button"
            className="mt-4 h-10 w-full"
            onClick={() => window.open(device.verification_uri_complete, "_blank", "noopener")}
          >
            {t("auth.deviceOpenHere")}
          </Button>
          <p className="mt-2 text-xs text-muted-foreground">{t("auth.deviceWaiting")}</p>
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
      {providers &&
        !providers.oauth.some((p) => p.enabled) &&
        !showDevice && (
          <p className="text-xs text-muted-foreground">{t("auth.oauthSetupHint")}</p>
        )}
    </div>
  );
}

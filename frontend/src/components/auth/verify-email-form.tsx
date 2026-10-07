"use client";
import * as React from "react";
import { AuthField, AuthLinkButton, AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { codeFromPasteEvent, normalizeVerificationCode } from "@/lib/auth-code";
import { useT } from "@/lib/i18n";
import { useAuthStore } from "@/store/auth-store";

function useCountdown(iso: string | null) {
  const [left, setLeft] = React.useState(0);
  React.useEffect(() => {
    if (!iso) {
      setLeft(0);
      return;
    }
    const tick = () => {
      const ms = new Date(iso).getTime() - Date.now();
      setLeft(Math.max(0, Math.ceil(ms / 1000)));
    };
    tick();
    const id = window.setInterval(tick, 500);
    return () => window.clearInterval(id);
  }, [iso]);
  return left;
}

export function VerifyEmailForm() {
  const t = useT();
  const email = useAuthStore((s) => s.pendingEmail);
  const codeExpiresAt = useAuthStore((s) => s.codeExpiresAt);
  const resendAvailableAt = useAuthStore((s) => s.resendAvailableAt);
  const verify = useAuthStore((s) => s.verify);
  const resend = useAuthStore((s) => s.resend);
  const setScreen = useAuthStore((s) => s.setScreen);
  const [code, setCode] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [info, setInfo] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const cooldown = useCountdown(resendAvailableAt);
  const expiresIn = useCountdown(codeExpiresAt);

  async function onVerify(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      await verify(code.trim());
      setInfo(t("auth.verifySuccess"));
      setScreen("login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
    } finally {
      setBusy(false);
    }
  }

  async function onResend() {
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      await resend();
      setInfo(t("auth.codeResent"));
    } catch (err) {
      if (err instanceof ApiError && err.retryAfterSeconds) {
        setError(t("auth.resendCooldown").replace("{seconds}", String(err.retryAfterSeconds)));
      } else {
        setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title={t("auth.verifyTitle")} subtitle={t("auth.verifySubtitle").replace("{email}", email)}>
      <form className="space-y-4" onSubmit={onVerify}>
        <AuthField label={t("auth.verificationCode")}>
          <Input
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            required
            value={code}
            onChange={(e) => setCode(normalizeVerificationCode(e.target.value))}
            onPaste={(e) => {
              e.preventDefault();
              setCode(codeFromPasteEvent(e));
            }}
            className="h-12 text-center text-2xl tracking-[0.35em]"
            autoFocus
          />
        </AuthField>
        <p className="text-center text-xs text-muted-foreground">
          {expiresIn > 0
            ? t("auth.codeExpiresIn").replace("{seconds}", String(expiresIn))
            : t("auth.codeExpiredHint")}
        </p>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {info && <p className="text-sm text-success">{info}</p>}
        <Button type="submit" className="h-10 w-full" disabled={busy || code.length !== 6}>
          {t("auth.verify")}
        </Button>
      </form>
      <div className="mt-5 flex flex-col items-center gap-2">
        <Button
          type="button"
          variant="outline"
          className="h-9 w-full"
          disabled={busy || cooldown > 0}
          onClick={() => void onResend()}
        >
          {cooldown > 0
            ? t("auth.resendIn").replace("{seconds}", String(cooldown))
            : t("auth.resendCode")}
        </Button>
        <AuthLinkButton onClick={() => setScreen("login")}>{t("auth.backToSignIn")}</AuthLinkButton>
      </div>
    </AuthShell>
  );
}

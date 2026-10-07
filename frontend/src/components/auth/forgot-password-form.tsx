"use client";
import * as React from "react";
import { AuthField, AuthLinkButton, AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { codeFromPasteEvent, normalizeVerificationCode } from "@/lib/auth-code";
import { useT } from "@/lib/i18n";
import { useAuthStore } from "@/store/auth-store";

export function ForgotPasswordForm() {
  const t = useT();
  const requestReset = useAuthStore((s) => s.requestReset);
  const setScreen = useAuthStore((s) => s.setScreen);
  const [email, setEmail] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await requestReset(email);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title={t("auth.forgotTitle")} subtitle={t("auth.forgotSubtitle")}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <AuthField label={t("auth.email")}>
          <Input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="h-10"
          />
        </AuthField>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="h-10 w-full" disabled={busy}>
          {t("auth.sendResetCode")}
        </Button>
      </form>
      <p className="mt-5 text-center">
        <AuthLinkButton onClick={() => setScreen("login")}>{t("auth.backToSignIn")}</AuthLinkButton>
      </p>
    </AuthShell>
  );
}

export function ResetPasswordForm() {
  const t = useT();
  const email = useAuthStore((s) => s.pendingEmail);
  const confirmReset = useAuthStore((s) => s.confirmReset);
  const setScreen = useAuthStore((s) => s.setScreen);
  const [code, setCode] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [info, setInfo] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    if (password !== confirm) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    setBusy(true);
    try {
      await confirmReset(code, password, confirm);
      setInfo(t("auth.resetSuccess"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title={t("auth.resetTitle")} subtitle={t("auth.resetSubtitle").replace("{email}", email)}>
      <form className="space-y-4" onSubmit={onSubmit}>
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
            className="h-10 tracking-widest"
          />
        </AuthField>
        <AuthField label={t("auth.newPassword")}>
          <Input
            type="password"
            required
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="h-10"
          />
        </AuthField>
        <AuthField label={t("auth.confirmPassword")}>
          <Input
            type="password"
            required
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="h-10"
          />
        </AuthField>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {info && <p className="text-sm text-success">{info}</p>}
        <Button type="submit" className="h-10 w-full" disabled={busy}>
          {t("auth.updatePassword")}
        </Button>
      </form>
      <p className="mt-5 text-center">
        <AuthLinkButton onClick={() => setScreen("login")}>{t("auth.backToSignIn")}</AuthLinkButton>
      </p>
    </AuthShell>
  );
}

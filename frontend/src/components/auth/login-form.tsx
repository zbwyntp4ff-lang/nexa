"use client";
import * as React from "react";
import { AuthField, AuthLinkButton, AuthShell } from "@/components/auth/auth-shell";
import { LoginProviders } from "@/components/auth/login-providers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { normalizeEmailInput } from "@/lib/normalize-email";
import { applyPasteToControlledInput } from "@/lib/paste-input";
import { useAuthStore } from "@/store/auth-store";

export function LoginForm() {
  const t = useT();
  const login = useAuthStore((s) => s.login);
  const setScreen = useAuthStore((s) => s.setScreen);
  const authStatus = useAuthStore((s) => s.authStatus);
  const pendingEmail = useAuthStore((s) => s.pendingEmail);
  const [email, setEmail] = React.useState(pendingEmail);
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const authError = params.get("auth_error");
    if (authError) {
      setError(t("auth.oauthFailed"));
      params.delete("auth_error");
      const next = params.toString();
      window.history.replaceState({}, "", next ? `?${next}` : window.location.pathname);
    }
  }, [t]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const cleanEmail = normalizeEmailInput(email);
    setEmail(cleanEmail);
    setBusy(true);
    try {
      await login(cleanEmail, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title={t("auth.loginTitle")} subtitle={t("auth.loginSubtitle")}>
      <form className="space-y-4" noValidate onSubmit={onSubmit}>
        <AuthField label={t("auth.emailOrUsername")}>
          <Input
            type="text"
            inputMode="email"
            autoComplete="username"
            name="email"
            spellCheck={false}
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={() => setEmail((v) => normalizeEmailInput(v))}
            onPaste={(e) => applyPasteToControlledInput(e, setEmail, { normalizeEmail: true })}
            className="h-10"
          />
        </AuthField>
        <AuthField label={t("auth.password")}>
          <Input
            type="password"
            autoComplete="current-password"
            name="password"
            spellCheck={false}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onPaste={(e) => applyPasteToControlledInput(e, setPassword)}
            className="h-10"
          />
        </AuthField>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="h-11 w-full" disabled={busy} data-testid="auth-sign-in">
          {busy ? t("auth.signingIn") : t("auth.signIn")}
        </Button>
      </form>
      <div className="mt-5">
        <LoginProviders />
      </div>
      <div className="mt-5 flex flex-col items-center gap-2">
        <AuthLinkButton onClick={() => setScreen("forgot")}>{t("auth.forgotPassword")}</AuthLinkButton>
        {authStatus?.registration_open && (
          <Button
            type="button"
            variant="outline"
            className="mt-2 w-full"
            data-testid="auth-create-account"
            onClick={() => setScreen("ownerSetup")}
          >
            {t("auth.createAccount")}
          </Button>
        )}
      </div>
    </AuthShell>
  );
}

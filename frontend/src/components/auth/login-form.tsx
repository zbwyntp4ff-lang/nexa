"use client";
import * as React from "react";
import { AuthField, AuthLinkButton, AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useAuthStore } from "@/store/auth-store";

export function LoginForm() {
  const t = useT();
  const login = useAuthStore((s) => s.login);
  const setScreen = useAuthStore((s) => s.setScreen);
  const authStatus = useAuthStore((s) => s.authStatus);
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title={t("auth.loginTitle")} subtitle={t("auth.loginSubtitle")}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <AuthField label={t("auth.email")}>
          <Input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="h-10"
          />
        </AuthField>
        <AuthField label={t("auth.password")}>
          <Input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="h-10"
          />
        </AuthField>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="h-10 w-full" disabled={busy}>
          {busy ? t("auth.signingIn") : t("auth.signIn")}
        </Button>
      </form>
      <div className="mt-5 flex flex-col items-center gap-2">
        <AuthLinkButton onClick={() => setScreen("forgot")}>{t("auth.forgotPassword")}</AuthLinkButton>
        {authStatus?.registration_open && (
          <Button type="button" variant="outline" className="mt-2 w-full" onClick={() => setScreen("ownerSetup")}>
            {t("auth.ownerButton")}
          </Button>
        )}
      </div>
    </AuthShell>
  );
}

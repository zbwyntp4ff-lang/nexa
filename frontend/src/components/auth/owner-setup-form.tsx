"use client";
import * as React from "react";
import { AuthField, AuthShell } from "@/components/auth/auth-shell";
import { LegalDocButton } from "@/components/auth/legal-doc-button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { normalizeEmailInput } from "@/lib/normalize-email";
import { applyPasteToControlledInput } from "@/lib/paste-input";
import { useAuthStore } from "@/store/auth-store";

/** Account registration (first owner setup or public multi-user sign-up). */
export function OwnerSetupForm() {
  const t = useT();
  const setupOwner = useAuthStore((s) => s.setupOwner);
  const setScreen = useAuthStore((s) => s.setScreen);
  const setPendingEmail = useAuthStore((s) => s.setPendingEmail);
  const hasUser = useAuthStore((s) => s.authStatus?.has_user);
  const title = hasUser ? t("auth.registerTitle") : t("auth.ownerTitle");
  const subtitle = hasUser ? t("auth.registerSubtitle") : t("auth.ownerSubtitle");
  const [form, setForm] = React.useState({
    first_name: "",
    last_name: "",
    username: "",
    email: "",
    password: "",
    confirm_password: "",
    accept_terms: true,
    accept_privacy: true,
    accept_license: true,
  });
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const cleanEmail = normalizeEmailInput(form.email);
    set("email", cleanEmail);
    if (form.password !== form.confirm_password) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    setBusy(true);
    try {
      await setupOwner({ ...form, email: cleanEmail });
    } catch (err) {
      if (err instanceof ApiError && (err.code === "UsernameTaken" || err.code === "EmailAlreadyRegistered")) {
        setPendingEmail(cleanEmail);
        setScreen("login");
        return;
      } else {
        setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title={title} subtitle={subtitle} className="max-w-lg">
      <Button
        type="button"
        className="mb-5 h-11 w-full"
        data-testid="auth-sign-in"
        onClick={() => setScreen("login")}
      >
        {t("auth.signIn")}
      </Button>
      <p className="mb-5 text-center text-xs text-muted-foreground">{t("auth.orCreateAccount")}</p>
      <form className="space-y-3.5" noValidate onSubmit={onSubmit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <AuthField label={t("auth.firstName")}>
            <Input
              required
              autoComplete="given-name"
              value={form.first_name}
              onChange={(e) => set("first_name", e.target.value)}
              className="h-10"
            />
          </AuthField>
          <AuthField label={t("auth.lastName")}>
            <Input
              required
              autoComplete="family-name"
              value={form.last_name}
              onChange={(e) => set("last_name", e.target.value)}
              className="h-10"
            />
          </AuthField>
        </div>
        <AuthField label={t("auth.username")}>
          <Input
            required
            autoComplete="username"
            value={form.username}
            onChange={(e) => set("username", e.target.value)}
            className="h-10"
          />
        </AuthField>
        <AuthField label={t("auth.email")}>
          <Input
            type="text"
            inputMode="email"
            required
            autoComplete="email"
            spellCheck={false}
            value={form.email}
            onChange={(e) => set("email", e.target.value)}
            onBlur={() => set("email", normalizeEmailInput(form.email))}
            onPaste={(e) =>
              applyPasteToControlledInput(e, (v) => set("email", v), { normalizeEmail: true })
            }
            className="h-10"
          />
        </AuthField>
        <AuthField label={t("auth.password")}>
          <Input
            type="password"
            required
            autoComplete="new-password"
            spellCheck={false}
            value={form.password}
            onChange={(e) => set("password", e.target.value)}
            onPaste={(e) => applyPasteToControlledInput(e, (v) => set("password", v))}
            className="h-10"
          />
        </AuthField>
        <AuthField label={t("auth.confirmPassword")}>
          <Input
            type="password"
            required
            autoComplete="new-password"
            spellCheck={false}
            value={form.confirm_password}
            onChange={(e) => set("confirm_password", e.target.value)}
            onPaste={(e) => applyPasteToControlledInput(e, (v) => set("confirm_password", v))}
            className="h-10"
          />
        </AuthField>
        <div className="space-y-2 rounded-lg border border-border/80 p-3">
          <label className="flex items-center gap-2 text-xs text-foreground">
            <input
              type="checkbox"
              checked={form.accept_terms}
              onChange={(e) => set("accept_terms", e.target.checked)}
            />
            <span>{t("auth.acceptTerms")}</span>
          </label>
          <label className="flex items-center gap-2 text-xs text-foreground">
            <input
              type="checkbox"
              checked={form.accept_privacy}
              onChange={(e) => set("accept_privacy", e.target.checked)}
            />
            <span>{t("auth.acceptPrivacy")}</span>
          </label>
          <label className="flex items-center gap-2 text-xs text-foreground">
            <input
              type="checkbox"
              checked={form.accept_license}
              onChange={(e) => set("accept_license", e.target.checked)}
            />
            <span>{t("auth.acceptLicense")}</span>
          </label>
          <div className="flex flex-col gap-1 pt-1">
            <LegalDocButton doc="terms_of_service" />
            <LegalDocButton doc="privacy_policy" />
            <LegalDocButton doc="license_agreement" />
          </div>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="h-11 w-full" disabled={busy}>
          {busy ? t("auth.ownerCreating") : t("auth.ownerButton")}
        </Button>
        <p className="text-center text-xs text-muted-foreground">{t("auth.ownerHint")}</p>
        <Button type="button" variant="outline" className="h-11 w-full" onClick={() => setScreen("login")}>
          {t("auth.haveAccount")} — {t("auth.signIn")}
        </Button>
      </form>
    </AuthShell>
  );
}

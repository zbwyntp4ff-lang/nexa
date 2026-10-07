"use client";
import * as React from "react";
import { AuthField, AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useAuthStore } from "@/store/auth-store";

/** One-time owner setup — replaces public registration (single-user mode). */
export function OwnerSetupForm() {
  const t = useT();
  const setupOwner = useAuthStore((s) => s.setupOwner);
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
    if (form.password !== form.confirm_password) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    setBusy(true);
    try {
      await setupOwner(form);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title={t("auth.ownerTitle")} subtitle={t("auth.ownerSubtitle")} className="max-w-lg">
      <form className="space-y-3.5" onSubmit={onSubmit}>
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
            type="email"
            required
            autoComplete="email"
            value={form.email}
            onChange={(e) => set("email", e.target.value)}
            className="h-10"
          />
        </AuthField>
        <AuthField label={t("auth.password")}>
          <Input
            type="password"
            required
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => set("password", e.target.value)}
            className="h-10"
          />
        </AuthField>
        <AuthField label={t("auth.confirmPassword")}>
          <Input
            type="password"
            required
            autoComplete="new-password"
            value={form.confirm_password}
            onChange={(e) => set("confirm_password", e.target.value)}
            className="h-10"
          />
        </AuthField>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="h-11 w-full" disabled={busy}>
          {busy ? t("auth.ownerCreating") : t("auth.ownerButton")}
        </Button>
        <p className="text-center text-xs text-muted-foreground">{t("auth.ownerHint")}</p>
      </form>
    </AuthShell>
  );
}

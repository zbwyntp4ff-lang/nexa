"use client";
import * as React from "react";
import { LegalDocButton } from "@/components/auth/legal-doc-button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import {
  fetchAuthProviders,
  fetchLegalIndex,
  passkeyRegisterOptions,
  passkeyRegisterVerify,
  saveGoogleOAuthConfig,
  saveLegalHolder,
  type LegalHolderKind,
} from "@/lib/auth-api";
import { passkeyCreate, webauthnSupported } from "@/lib/webauthn";
import { useT } from "@/lib/i18n";
import { useAuthStore } from "@/store/auth-store";

export function PrivacySection() {
  const t = useT();
  const user = useAuthStore((s) => s.user);
  const [passkeyMsg, setPasskeyMsg] = React.useState<string | null>(null);
  const [passkeyBusy, setPasskeyBusy] = React.useState(false);
  const [googleId, setGoogleId] = React.useState("");
  const [googleSecret, setGoogleSecret] = React.useState("");
  const [googleMsg, setGoogleMsg] = React.useState<string | null>(null);
  const [googleBusy, setGoogleBusy] = React.useState(false);
  const [googleOn, setGoogleOn] = React.useState(false);
  const [holderName, setHolderName] = React.useState("");
  const [holderKind, setHolderKind] = React.useState<LegalHolderKind>("individual");
  const [holderContact, setHolderContact] = React.useState("");
  const [holderInn, setHolderInn] = React.useState("");
  const [holderBusy, setHolderBusy] = React.useState(false);
  const [holderMsg, setHolderMsg] = React.useState<string | null>(null);
  const deleteMyAccount = useAuthStore((s) => s.deleteMyAccount);
  const [deleteBusy, setDeleteBusy] = React.useState(false);
  const [deleteMsg, setDeleteMsg] = React.useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = React.useState("");

  React.useEffect(() => {
    void fetchAuthProviders()
      .then((p) => setGoogleOn(Boolean(p.oauth.find((o) => o.id === "google")?.enabled)))
      .catch(() => undefined);
    void fetchLegalIndex()
      .then((data) => {
        setHolderName(data.holder.name);
        setHolderKind(data.holder.kind);
        setHolderContact(data.holder.contact);
        setHolderInn(data.holder.inn);
      })
      .catch(() => undefined);
  }, []);

  async function addPasskey() {
    setPasskeyMsg(null);
    if (!webauthnSupported()) {
      setPasskeyMsg(t("auth.passkeyUnsupported"));
      return;
    }
    setPasskeyBusy(true);
    try {
      const options = await passkeyRegisterOptions();
      const assertion = await passkeyCreate(options as unknown as PublicKeyCredentialCreationOptions);
      await passkeyRegisterVerify({ ...assertion, label: "NEXA" });
      setPasskeyMsg(t("auth.passkeyRegistered"));
    } catch (err) {
      setPasskeyMsg(err instanceof ApiError ? err.message : t("auth.passkeyFailed"));
    } finally {
      setPasskeyBusy(false);
    }
  }

  async function saveHolder() {
    setHolderMsg(null);
    setHolderBusy(true);
    try {
      const saved = await saveLegalHolder({
        name: holderName.trim(),
        kind: holderKind,
        contact: holderContact.trim(),
        inn: holderInn.trim(),
        country: "RU",
      });
      setHolderName(saved.holder.name);
      setHolderKind(saved.holder.kind);
      setHolderContact(saved.holder.contact);
      setHolderInn(saved.holder.inn);
      setHolderMsg(t("auth.legalHolderSaved"));
    } catch (err) {
      setHolderMsg(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
    } finally {
      setHolderBusy(false);
    }
  }

  async function saveGoogle() {
    setGoogleMsg(null);
    setGoogleBusy(true);
    try {
      await saveGoogleOAuthConfig(googleId.trim(), googleSecret.trim());
      setGoogleOn(true);
      setGoogleSecret("");
      setGoogleMsg(t("auth.googleSaved"));
    } catch (err) {
      setGoogleMsg(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
    } finally {
      setGoogleBusy(false);
    }
  }

  return (
    <div className="space-y-6 text-sm text-muted-foreground">
      <h3 className="text-sm font-medium text-foreground">{t("privacy.title")}</h3>
      <ul className="list-disc space-y-2 pl-5">
        <li>{t("privacy.point1")}</li>
        <li>{t("privacy.point2")}</li>
        <li>{t("privacy.point3")}</li>
        <li>{t("privacy.point4")}</li>
        <li>{t("privacy.point5")}</li>
      </ul>

      {user && (
        <div className="space-y-2 rounded-md border border-destructive/40 p-3">
          <h4 className="text-sm font-medium text-foreground">{t("privacy.deleteAccount")}</h4>
          <p className="text-xs">{t("privacy.deleteAccountDesc")}</p>
          <Input
            className="h-9"
            value={deleteConfirm}
            onChange={(e) => setDeleteConfirm(e.target.value)}
            placeholder={t("privacy.deleteAccountConfirmPlaceholder")}
            autoComplete="off"
            aria-label={t("privacy.deleteAccountConfirmPlaceholder")}
          />
          <Button
            type="button"
            variant="destructive"
            className="h-9"
            disabled={deleteBusy || deleteConfirm.trim().toUpperCase() !== "DELETE"}
            onClick={() => {
              setDeleteMsg(null);
              setDeleteBusy(true);
              void deleteMyAccount()
                .then(() => setDeleteMsg(t("privacy.deleteAccountDone")))
                .catch((err) =>
                  setDeleteMsg(err instanceof ApiError ? err.message : t("auth.errorGeneric")),
                )
                .finally(() => setDeleteBusy(false));
            }}
          >
            {deleteBusy ? t("auth.signingIn") : t("privacy.deleteAccountAction")}
          </Button>
          {deleteMsg && <p className="text-xs text-foreground">{deleteMsg}</p>}
        </div>
      )}

      <div className="space-y-2">
        <h4 className="text-sm font-medium text-foreground">{t("auth.legalTitle")}</h4>
        <div className="flex flex-col gap-1">
          <LegalDocButton doc="terms_of_service" />
          <LegalDocButton doc="privacy_policy" />
          <LegalDocButton doc="license_agreement" />
        </div>
        <p className="text-xs">{t("auth.legalDropHint")}</p>
      </div>

      {user?.is_owner && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-foreground">{t("auth.legalHolderTitle")}</h4>
          <p>{t("auth.legalHolderHint")}</p>
          <label className="block text-xs text-foreground">{t("auth.legalHolderName")}</label>
          <Input
            className="h-9"
            value={holderName}
            onChange={(e) => setHolderName(e.target.value)}
            autoComplete="organization"
          />
          <label className="block text-xs text-foreground">{t("auth.legalHolderKind")}</label>
          <select
            className="h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm text-foreground"
            value={holderKind}
            onChange={(e) => setHolderKind(e.target.value as LegalHolderKind)}
          >
            <option value="individual">{t("auth.legalHolderKind.individual")}</option>
            <option value="sole_proprietor">{t("auth.legalHolderKind.sole_proprietor")}</option>
            <option value="company">{t("auth.legalHolderKind.company")}</option>
          </select>
          <label className="block text-xs text-foreground">{t("auth.legalHolderContact")}</label>
          <Input
            className="h-9"
            value={holderContact}
            onChange={(e) => setHolderContact(e.target.value)}
            autoComplete="email"
          />
          <label className="block text-xs text-foreground">{t("auth.legalHolderInn")}</label>
          <Input
            className="h-9"
            value={holderInn}
            onChange={(e) => setHolderInn(e.target.value)}
            inputMode="numeric"
            autoComplete="off"
          />
          <Button
            type="button"
            className="h-9"
            disabled={holderBusy || holderName.trim().length < 2}
            onClick={() => void saveHolder()}
          >
            {holderBusy ? t("auth.signingIn") : t("auth.legalHolderSave")}
          </Button>
          {holderMsg && <p className="text-xs text-foreground">{holderMsg}</p>}
        </div>
      )}

      <div className="space-y-2">
        <h4 className="text-sm font-medium text-foreground">{t("auth.passkey")}</h4>
        <p>{t("auth.passkeyAddHint")}</p>
        <Button type="button" className="h-9" disabled={passkeyBusy} onClick={() => void addPasskey()}>
          {passkeyBusy ? t("auth.signingIn") : t("auth.passkeyAdd")}
        </Button>
        {passkeyMsg && <p className="text-xs text-foreground">{passkeyMsg}</p>}
      </div>

      {user?.is_owner && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-foreground">Google</h4>
          <p>{googleOn ? t("auth.googleEnabled") : t("auth.googleSetupHint")}</p>
          <Input
            className="h-9"
            placeholder="Client ID"
            value={googleId}
            onChange={(e) => setGoogleId(e.target.value)}
            autoComplete="off"
          />
          <Input
            className="h-9"
            type="password"
            placeholder="Client Secret"
            value={googleSecret}
            onChange={(e) => setGoogleSecret(e.target.value)}
            autoComplete="off"
          />
          <Button
            type="button"
            className="h-9"
            disabled={googleBusy || googleId.trim().length < 8 || googleSecret.trim().length < 8}
            onClick={() => void saveGoogle()}
          >
            {googleBusy ? t("auth.signingIn") : t("auth.googleSave")}
          </Button>
          {googleMsg && <p className="text-xs text-foreground">{googleMsg}</p>}
        </div>
      )}
    </div>
  );
}

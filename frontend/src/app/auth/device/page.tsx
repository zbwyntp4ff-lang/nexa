"use client";
import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthField, AuthShell } from "@/components/auth/auth-shell";
import { LoginForm } from "@/components/auth/login-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { approveDeviceLogin } from "@/lib/auth-api";
import { useT } from "@/lib/i18n";
import { useAuthStore } from "@/store/auth-store";

function DeviceApproveInner() {
  const t = useT();
  const router = useRouter();
  const params = useSearchParams();
  const status = useAuthStore((s) => s.status);
  const bootstrap = useAuthStore((s) => s.bootstrap);
  const [code, setCode] = React.useState(params.get("code") || "");
  const [error, setError] = React.useState<string | null>(null);
  const [done, setDone] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  React.useEffect(() => {
    const fromUrl = params.get("code");
    if (fromUrl) setCode(fromUrl);
  }, [params]);

  const approve = React.useCallback(
    async (userCode: string) => {
      setError(null);
      setBusy(true);
      try {
        await approveDeviceLogin(userCode.trim());
        setDone(true);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : t("auth.errorGeneric"));
      } finally {
        setBusy(false);
      }
    },
    [t],
  );

  const autoTried = React.useRef(false);
  React.useEffect(() => {
    if (status !== "authenticated" || done || autoTried.current || !code.trim()) return;
    autoTried.current = true;
    void approve(code);
  }, [status, done, code, approve]);

  if (status === "loading") {
    return (
      <div className="flex h-dvh items-center justify-center text-sm text-muted-foreground">NEXA</div>
    );
  }

  if (status !== "authenticated") {
    return (
      <div className="space-y-4">
        <p className="px-4 pt-6 text-center text-sm text-muted-foreground">{t("auth.deviceLoginFirst")}</p>
        <LoginForm />
      </div>
    );
  }

  return (
    <AuthShell title={t("auth.deviceApproveTitle")} subtitle={t("auth.deviceApproveSubtitle")}>
      {done ? (
        <p className="text-sm text-foreground">{t("auth.deviceApproved")}</p>
      ) : (
        <div className="space-y-4">
          <AuthField label={t("auth.deviceCode")}>
            <Input
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              className="h-10 font-mono tracking-widest"
              placeholder="ABC-DEF"
              autoComplete="one-time-code"
            />
          </AuthField>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button
            type="button"
            className="h-10 w-full"
            disabled={busy || code.trim().length < 5}
            onClick={() => void approve(code)}
          >
            {busy ? t("auth.signingIn") : t("auth.deviceApprove")}
          </Button>
          <Button type="button" variant="outline" className="h-10 w-full" onClick={() => router.push("/")}>
            {t("auth.backToSignIn")}
          </Button>
        </div>
      )}
    </AuthShell>
  );
}

export default function DeviceApprovePage() {
  return (
    <React.Suspense
      fallback={
        <div className="flex h-dvh items-center justify-center text-sm text-muted-foreground">NEXA</div>
      }
    >
      <DeviceApproveInner />
    </React.Suspense>
  );
}

"use client";
import * as React from "react";
import { ForgotPasswordForm, ResetPasswordForm } from "@/components/auth/forgot-password-form";
import { LoginForm } from "@/components/auth/login-form";
import { OnboardingDialog } from "@/components/auth/onboarding-dialog";
import { OwnerSetupForm } from "@/components/auth/owner-setup-form";
import { VerifyEmailForm } from "@/components/auth/verify-email-form";
import { setSessionToken } from "@/lib/session-token";
import { useAuthStore } from "@/store/auth-store";
import { useProfileStore } from "@/store/profile-store";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const status = useAuthStore((s) => s.status);
  const screen = useAuthStore((s) => s.screen);
  const registrationOpen = useAuthStore((s) => s.authStatus?.registration_open);
  const bootstrap = useAuthStore((s) => s.bootstrap);
  const profile = useProfileStore((s) => s.profile);
  const loadProfile = useProfileStore((s) => s.load);
  const [onboardingDismissed, setOnboardingDismissed] = React.useState(false);

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      // Legacy: older OAuth callbacks put session_token in the URL. Prefer cookie.
      const token = params.get("session_token");
      if (token) {
        setSessionToken(token);
        params.delete("session_token");
      }
      if (params.get("oauth") === "ok") {
        params.delete("oauth");
      }
      if (token || params.toString() !== window.location.search.slice(1)) {
        const next = params.toString();
        window.history.replaceState({}, "", next ? `?${next}` : window.location.pathname);
      }
    }
    void bootstrap();
  }, [bootstrap]);

  React.useEffect(() => {
    if (status === "authenticated") void loadProfile();
  }, [status, loadProfile]);

  if (status === "loading") {
    return (
      <div className="flex h-dvh w-full items-center justify-center bg-background text-sm text-muted-foreground">
        NEXA
      </div>
    );
  }

  if (status !== "authenticated") {
    if (screen === "verify") return <VerifyEmailForm />;
    if (screen === "forgot") return <ForgotPasswordForm />;
    if (screen === "reset") return <ResetPasswordForm />;
    // Multi-user: registration stays available whenever the API says so.
    if (screen === "ownerSetup" && registrationOpen !== false) return <OwnerSetupForm />;
    return <LoginForm />;
  }

  const needsOnboarding = profile !== null && !profile.onboarding_completed && !onboardingDismissed;

  return (
    <>
      {needsOnboarding && <OnboardingDialog onDone={() => setOnboardingDismissed(true)} />}
      {children}
    </>
  );
}

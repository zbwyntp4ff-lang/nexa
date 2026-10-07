"use client";
import * as React from "react";
import { ForgotPasswordForm, ResetPasswordForm } from "@/components/auth/forgot-password-form";
import { LoginForm } from "@/components/auth/login-form";
import { OwnerSetupForm } from "@/components/auth/owner-setup-form";
import { VerifyEmailForm } from "@/components/auth/verify-email-form";
import { useAuthStore } from "@/store/auth-store";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const status = useAuthStore((s) => s.status);
  const screen = useAuthStore((s) => s.screen);
  const bootstrap = useAuthStore((s) => s.bootstrap);

  React.useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  if (status === "loading") {
    return (
      <div className="flex h-dvh w-full items-center justify-center bg-background text-sm text-muted-foreground">
        NEXA
      </div>
    );
  }

  if (status !== "authenticated") {
    if (screen === "ownerSetup") return <OwnerSetupForm />;
    if (screen === "verify") return <VerifyEmailForm />;
    if (screen === "forgot") return <ForgotPasswordForm />;
    if (screen === "reset") return <ResetPasswordForm />;
    return <LoginForm />;
  }

  return <>{children}</>;
}

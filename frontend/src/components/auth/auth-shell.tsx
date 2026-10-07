"use client";
import * as React from "react";
import { LogoWordmark } from "@/components/common/logo";
import { cn } from "@/lib/utils";

export function AuthShell({
  title,
  subtitle,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className="nexa-chat-atmosphere flex min-h-dvh w-full items-center justify-center px-4 py-10 text-foreground">
      <div
        className={cn(
          "w-full max-w-md rounded-2xl border border-border/80 bg-background/85 p-6 shadow-xl backdrop-blur-md sm:p-8",
          className
        )}
      >
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <LogoWordmark />
          <div className="space-y-1">
            <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
            {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}

export function AuthField({
  label,
  children,
  error,
}: {
  label: string;
  children: React.ReactNode;
  error?: string;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium text-foreground/90">{label}</span>
      {children}
      {error && <span className="text-xs text-destructive">{error}</span>}
    </label>
  );
}

export function AuthLinkButton({
  children,
  onClick,
  className,
}: {
  children: React.ReactNode;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className
      )}
    >
      {children}
    </button>
  );
}

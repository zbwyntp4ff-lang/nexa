"use client";

import * as React from "react";
import Link from "next/link";
import { Clock, Sparkles, X } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { fetchBillingMe } from "@/lib/billing-api";
import { fetchTokenBalance } from "@/lib/tokens-api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { TOKEN_WAIT_MS, usePlanPromoStore } from "@/store/plan-promo-store";

function formatRemaining(ms: number): string {
  if (ms <= 0) return "0:00";
  const totalMin = Math.ceil(ms / 60_000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return `${h}:${String(m).padStart(2, "0")}`;
}

/**
 * Overlay promo — does not live in the sidebar (Settings / profile stay free).
 * - limit: credits/limits exhausted → buy plan or wait 10h
 * - soft: occasional nudge (dismissible)
 */
export function PlanPromoDialog() {
  const t = useT();
  const mode = usePlanPromoStore((s) => s.mode);
  const waitUntil = usePlanPromoStore((s) => s.waitUntil);
  const dismiss = usePlanPromoStore((s) => s.dismiss);
  const openLimit = usePlanPromoStore((s) => s.openLimit);
  const openSoftMaybe = usePlanPromoStore((s) => s.openSoftMaybe);
  const [now, setNow] = React.useState(() => Date.now());
  const [paid, setPaid] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    fetchBillingMe()
      .then((data) => {
        if (!cancelled && data.plan && data.plan !== "free") setPaid(true);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Occasional soft promo + detect already-empty balance on load.
  React.useEffect(() => {
    if (paid) return;
    const softTimer = window.setTimeout(() => openSoftMaybe(), 8_000);
    let cancelled = false;
    fetchTokenBalance()
      .then((b) => {
        if (cancelled || paid) return;
        const dailyFull = b.daily_limit > 0 && b.daily_spent >= b.daily_limit;
        const monthlyFull = b.monthly_limit > 0 && b.monthly_spent >= b.monthly_limit;
        if (b.balance <= 0 || dailyFull || monthlyFull) openLimit();
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      window.clearTimeout(softTimer);
    };
  }, [paid, openLimit, openSoftMaybe]);

  React.useEffect(() => {
    if (mode !== "limit" || !waitUntil) return;
    const id = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, [mode, waitUntil]);

  React.useEffect(() => {
    if (mode === "limit" && waitUntil && Date.now() >= waitUntil) {
      dismiss();
    }
  }, [mode, waitUntil, now, dismiss]);

  if (paid || mode === "hidden") return null;

  const remainingMs = waitUntil ? Math.max(0, waitUntil - now) : TOKEN_WAIT_MS;
  const open = mode === "limit" || mode === "soft";

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) dismiss();
      }}
    >
      <DialogContent
        className="max-w-md gap-4"
        data-testid="plan-promo-dialog"
        showCloseButton={mode === "soft"}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="size-4 text-primary" aria-hidden />
            {mode === "limit" ? t("planPromo.limitTitle") : t("planPromo.softTitle")}
          </DialogTitle>
          <DialogDescription>
            {mode === "limit" ? t("planPromo.limitDesc") : t("planPromo.softDesc")}
          </DialogDescription>
        </DialogHeader>

        {mode === "limit" && (
          <p className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
            <Clock className="size-4 shrink-0" aria-hidden />
            {t("planPromo.waitCountdown", { time: formatRemaining(remainingMs) })}
          </p>
        )}

        <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
          {mode === "limit" ? (
            <>
              <Button type="button" variant="outline" onClick={() => dismiss()}>
                {t("planPromo.waitCta")}
              </Button>
              <Link
                href="/pricing"
                className={cn(buttonVariants())}
                onClick={() => dismiss()}
              >
                {t("planPromo.buyCta")}
              </Link>
            </>
          ) : (
            <>
              <Button type="button" variant="ghost" onClick={() => dismiss()}>
                <X className="size-3.5" aria-hidden />
                {t("planPromo.dismiss")}
              </Button>
              <Link
                href="/pricing"
                className={cn(buttonVariants({ size: "sm" }))}
                onClick={() => dismiss()}
              >
                {t("planPromo.buyCta")}
              </Link>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

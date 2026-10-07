"use client";

import * as React from "react";
import Link from "next/link";
import { Check, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { LogoWordmark } from "@/components/common/logo";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  createCheckout,
  fetchPlans,
  formatRub,
  isBillingApiError,
  type BillingInterval,
  type PlanId,
  type PlanPublic,
} from "@/lib/billing-api";
import { cn } from "@/lib/utils";

function ComparisonMatrix({ plans }: { plans: PlanPublic[] }) {
  const featureIds = Array.from(
    new Set(plans.flatMap((p) => p.features.map((f) => f.id)))
  );
  const labels = Object.fromEntries(
    plans.flatMap((p) => p.features.map((f) => [f.id, f.label]))
  );
  return (
    <div className="mt-16 overflow-x-auto rounded-2xl border border-border/60 bg-background/40 backdrop-blur-md">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-border/60">
            <th className="px-4 py-3 font-medium text-muted-foreground">Capability</th>
            {plans.map((p) => (
              <th key={p.id} className={cn("px-4 py-3 font-semibold", p.popular && "text-primary")}>
                {p.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {featureIds.map((fid) => (
            <tr key={fid} className="border-b border-border/40">
              <td className="px-4 py-2.5 text-muted-foreground">{labels[fid] ?? fid}</td>
              {plans.map((p) => {
                const on = p.features.some((f) => f.id === fid);
                return (
                  <td key={p.id} className="px-4 py-2.5">
                    {on ? <Check className="size-4 text-primary" aria-label="included" /> : (
                      <span className="text-muted-foreground/40">—</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
          <tr>
            <td className="px-4 py-2.5 text-muted-foreground">Experiments / month</td>
            {plans.map((p) => (
              <td key={p.id} className="px-4 py-2.5 font-medium">
                {p.experiment_limit === null
                  ? "Unlimited"
                  : p.experiment_limit === 0
                    ? "—"
                    : p.experiment_limit}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export default function PricingPage() {
  const [interval, setInterval] = React.useState<BillingInterval>("month");
  const [plans, setPlans] = React.useState<PlanPublic[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [busyPlan, setBusyPlan] = React.useState<PlanId | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void fetchPlans()
      .then((res) => {
        if (!cancelled) setPlans(res.plans);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load plans.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSelect(plan: PlanPublic) {
    if (plan.id === "free") {
      window.location.href = "/";
      return;
    }
    if (plan.contact_sales) {
      window.location.href = `mailto:sales@nexa.ai?subject=NEXA%20Enterprise`;
      return;
    }
    setBusyPlan(plan.id);
    try {
      const origin = window.location.origin;
      const session = await createCheckout({
        plan: plan.id,
        interval,
        success_url: `${origin}/pricing?checkout=success`,
        cancel_url: `${origin}/pricing?checkout=cancel`,
      });
      // Real Stripe Checkout — never fake isPaid on the client.
      window.location.href = session.checkout_url;
    } catch (err) {
      const message = isBillingApiError(err)
        ? err.message
        : err instanceof Error
          ? err.message
          : "Checkout failed.";
      toast.error(message);
      setBusyPlan(null);
    }
  }

  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("checkout") === "success") {
      toast.success("Payment received. Your plan activates after webhook confirmation.");
    }
    if (params.get("checkout") === "cancel") {
      toast.message("Checkout canceled — no charge was made.");
    }
  }, []);

  return (
    <div className="nexa-chat-atmosphere relative min-h-dvh overflow-hidden text-foreground">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-10%,color-mix(in_oklch,var(--nexa-violet),transparent_55%),transparent_70%),radial-gradient(ellipse_60%_40%_at_90%_20%,color-mix(in_oklch,var(--nexa-cyan),transparent_70%),transparent_65%)]"
      />
      <header className="relative mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-5">
        <Link href="/" className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <LogoWordmark className="text-xl" />
        </Link>
        <Link href="/" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
          Open NEXA
        </Link>
      </header>

      <main className="relative mx-auto w-full max-w-6xl px-6 pb-24 pt-6">
        <p className="text-[11px] font-semibold tracking-[0.2em] text-muted-foreground uppercase">
          Pricing
        </p>
        <h1 className="mt-2 max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">
          NEXA
        </h1>
        <p className="mt-3 max-w-xl text-base text-muted-foreground sm:text-lg">
          Real subscriptions. Real Stripe Checkout. Access unlocks only after a verified webhook —
          never a frontend paywall flag.
        </p>

        <div className="mt-8 inline-flex rounded-xl border border-border/70 bg-background/50 p-1 backdrop-blur-md">
          {(["month", "year"] as const).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setInterval(id)}
              className={cn(
                "rounded-lg px-4 py-2 text-sm font-medium transition-colors",
                interval === id
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {id === "month" ? "Monthly" : "Yearly"}
              {id === "year" && (
                <span className="ml-2 text-[10px] font-semibold tracking-wide uppercase opacity-90">
                  Save ~17%
                </span>
              )}
            </button>
          ))}
        </div>

        {loading && (
          <div className="mt-16 flex items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" aria-hidden />
            Loading plans…
          </div>
        )}

        {error && !loading && (
          <div className="mt-12 rounded-2xl border border-destructive/40 bg-destructive/10 px-5 py-4 text-sm">
            <p className="font-medium">Could not load pricing</p>
            <p className="mt-1 text-muted-foreground">{error}</p>
            <Button className="mt-3" variant="outline" onClick={() => window.location.reload()}>
              Retry
            </Button>
          </div>
        )}

        {plans && !loading && (
          <>
            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              {plans.map((plan) => {
                const amount =
                  interval === "year" ? plan.yearly_amount : plan.monthly_amount;
                const busy = busyPlan === plan.id;
                return (
                  <article
                    key={plan.id}
                    className={cn(
                      "relative flex flex-col rounded-2xl border p-5 backdrop-blur-md transition-shadow",
                      plan.popular
                        ? "border-primary/60 bg-primary/10 shadow-[0_0_40px_-12px_var(--nexa-violet)]"
                        : "border-border/60 bg-background/40"
                    )}
                  >
                    {plan.highlight && (
                      <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 rounded-full bg-primary px-2.5 py-0.5 text-[10px] font-bold tracking-wide text-primary-foreground uppercase">
                        {plan.highlight}
                      </span>
                    )}
                    <div className="flex items-center gap-2">
                      {plan.popular && <Sparkles className="size-4 text-primary" aria-hidden />}
                      <h2 className="text-lg font-semibold">{plan.name}</h2>
                    </div>
                    <p className="mt-1 min-h-10 text-sm text-muted-foreground">{plan.tagline}</p>
                    <p className="mt-4 text-3xl font-semibold tracking-tight">
                      {formatRub(amount)}
                      {!plan.contact_sales && amount > 0 && (
                        <span className="text-sm font-normal text-muted-foreground">
                          /{interval === "year" ? "yr" : "mo"}
                        </span>
                      )}
                    </p>
                    {interval === "year" && plan.yearly_savings_percent != null && (
                      <p className="mt-1 text-xs text-primary">
                        Save {plan.yearly_savings_percent}% vs monthly
                      </p>
                    )}
                    <ul className="mt-4 flex-1 space-y-2 text-sm">
                      {plan.features.length === 0 && (
                        <li className="text-muted-foreground">Core chat & agent</li>
                      )}
                      {plan.features.map((f) => (
                        <li key={f.id} className="flex gap-2">
                          <Check className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden />
                          <span>{f.label}</span>
                        </li>
                      ))}
                      {plan.experiment_limit !== 0 && (
                        <li className="flex gap-2 text-muted-foreground">
                          <Check className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden />
                          <span>
                            {plan.experiment_limit == null
                              ? "Unlimited experiments"
                              : `${plan.experiment_limit} experiments / mo`}
                          </span>
                        </li>
                      )}
                    </ul>
                    <Button
                      className="mt-5 w-full"
                      variant={plan.popular ? "default" : "outline"}
                      disabled={busy}
                      onClick={() => void onSelect(plan)}
                    >
                      {busy ? <Loader2 className="size-4 animate-spin" /> : plan.cta}
                    </Button>
                  </article>
                );
              })}
            </div>
            <ComparisonMatrix plans={plans} />
          </>
        )}
      </main>
    </div>
  );
}

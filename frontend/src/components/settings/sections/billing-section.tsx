"use client";

import * as React from "react";
import Link from "next/link";
import { CreditCard, ExternalLink, Loader2, Receipt } from "lucide-react";
import { toast } from "sonner";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  cancelSubscription,
  createPortal,
  detachPaymentMethod,
  fetchBillingMe,
  formatRub,
  isBillingApiError,
  resumeSubscription,
  type BillingOverview,
} from "@/lib/billing-api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function BillingSection() {
  const t = useT();
  const [data, setData] = React.useState<BillingOverview | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState<string | null>(null);

  const reload = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchBillingMe());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load billing.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void reload();
  }, [reload]);

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    try {
      await fn();
      await reload();
    } catch (err) {
      toast.error(isBillingApiError(err) ? err.message : "Billing action failed.");
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> {t("billing.loading")}
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" onClick={() => void reload()}>
          {t("billing.retry")}
        </Button>
      </div>
    );
  }

  if (!data) return null;

  const nextPayment = data.current_period_end
    ? new Date(data.current_period_end).toLocaleString()
    : "—";

  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-sm font-medium">{t("billing.title")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("billing.desc")}</p>
      </div>

      <section className="rounded-xl border border-border p-4">
        <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          {t("billing.currentPlan")}
        </p>
        <p className="mt-1 text-2xl font-semibold capitalize">
          {data.plan_name}{" "}
          <span className="text-sm font-normal text-muted-foreground">({data.status})</span>
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("billing.interval")}: {data.billing_interval}
          {data.cancel_at_period_end ? ` · ${t("billing.cancelsAtEnd")}` : ""}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("billing.nextPayment")}: {nextPayment}
        </p>
        {data.provider_status && (
          <p className="mt-3 text-xs text-muted-foreground" data-testid="billing-provider-status">
            {t("billing.providerMode", {
              provider: data.provider_status.provider,
              mode: data.provider_status.mode,
              activation: data.provider_status.activation,
            })}
          </p>
        )}
        {!data.provider_configured && (
          <p className="mt-2 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
            {t("billing.notConfigured")}
          </p>
        )}
        {data.provider_configured && data.provider_status?.mode === "test" && (
          <p className="mt-2 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
            {t("billing.providerTest")}
          </p>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <Link href="/pricing" className={cn(buttonVariants({ size: "sm" }))}>
            {t("billing.changePlan")}
          </Link>
          <Button
            size="sm"
            variant="outline"
            disabled={busy !== null || !data.provider_configured}
            onClick={() =>
              void run("portal", async () => {
                const { portal_url } = await createPortal(`${window.location.origin}/`);
                window.location.href = portal_url;
              })
            }
          >
            {busy === "portal" ? <Loader2 className="size-4 animate-spin" /> : t("billing.updatePayment")}
          </Button>
          {data.plan !== "free" && !data.cancel_at_period_end && (
            <Button
              size="sm"
              variant="ghost"
              disabled={busy !== null}
              onClick={() =>
                void run("cancel", async () => {
                  await cancelSubscription();
                  toast.success(t("billing.cancelScheduled"));
                })
              }
            >
              {t("billing.cancel")}
            </Button>
          )}
          {data.cancel_at_period_end && (
            <Button
              size="sm"
              variant="secondary"
              disabled={busy !== null}
              onClick={() =>
                void run("resume", async () => {
                  await resumeSubscription();
                  toast.success(t("billing.resumed"));
                })
              }
            >
              {t("billing.resume")}
            </Button>
          )}
        </div>
      </section>

      <section className="space-y-2">
        <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          {t("billing.usage")}
        </p>
        <div className="rounded-xl border border-border p-4 text-sm">
          <p>
            {t("billing.experiments")}: {data.usage.experiments_used}
            {data.usage.experiments_limit == null
              ? " / ∞"
              : ` / ${data.usage.experiments_limit}`}
          </p>
          <p className="mt-1 text-muted-foreground">
            {t("billing.period")}: {data.usage.period}
          </p>
        </div>
      </section>

      <section className="space-y-2">
        <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          {t("billing.paymentMethods")}
        </p>
        {data.payment_methods.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("billing.noPaymentMethods")}</p>
        ) : (
          <ul className="space-y-2">
            {data.payment_methods.map((pm) => (
              <li
                key={pm.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-border px-3 py-2 text-sm"
              >
                <span className="flex items-center gap-2">
                  <CreditCard className="size-4 text-muted-foreground" aria-hidden />
                  {(pm.brand || "card").toUpperCase()} ···· {pm.last4}
                  <span className="text-muted-foreground">
                    {pm.exp_month}/{pm.exp_year}
                  </span>
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={busy !== null}
                  onClick={() =>
                    void run(`detach:${pm.id}`, async () => {
                      await detachPaymentMethod(pm.id);
                      toast.success(t("billing.methodRemoved"));
                    })
                  }
                >
                  {t("billing.remove")}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          {t("billing.invoices")}
        </p>
        {data.invoices.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("billing.noInvoices")}</p>
        ) : (
          <ul className="space-y-2">
            {data.invoices.map((inv) => (
              <li
                key={inv.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-border px-3 py-2 text-sm"
              >
                <span className="flex items-center gap-2">
                  <Receipt className="size-4 text-muted-foreground" aria-hidden />
                  {formatRub(inv.amount)} · {inv.status}
                </span>
                {inv.invoice_url && (
                  <a
                    href={inv.invoice_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    {t("billing.open")} <ExternalLink className="size-3" />
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          {t("billing.paymentHistory")}
        </p>
        {data.payments.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("billing.noPayments")}</p>
        ) : (
          <ul className="space-y-2">
            {data.payments.map((p) => (
              <li key={p.id} className="rounded-xl border border-border px-3 py-2 text-sm">
                {formatRub(p.amount)} · {p.status}
                {p.description ? ` · ${p.description}` : ""}
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  {new Date(p.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

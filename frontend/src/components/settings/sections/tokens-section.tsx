"use client";

import * as React from "react";
import { Coins, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  isTokensApiError,
  kindLabel,
  type UsageByReason,
} from "@/lib/tokens-api";
import { useT } from "@/lib/i18n";
import { useTokensStore } from "@/store/tokens-store";
import { cn } from "@/lib/utils";

function UsageBar({
  label,
  spent,
  limit,
  period,
  remainingLabel,
}: {
  label: string;
  spent: number;
  limit: number;
  period: string;
  remainingLabel: string | null;
}) {
  const pct =
    limit > 0 ? Math.min(100, Math.round((spent / limit) * 100)) : spent > 0 ? 100 : 0;
  return (
    <div className="rounded-xl border border-border p-4">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          {label}
        </p>
        <p className="text-xs text-muted-foreground">{period || "—"}</p>
      </div>
      <p className="mt-1 text-lg font-semibold tabular-nums">
        {spent}
        <span className="text-sm font-normal text-muted-foreground">
          {" "}
          / {limit > 0 ? limit : "∞"}
        </span>
      </p>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-[width]",
            pct >= 90 ? "bg-destructive" : pct >= 70 ? "bg-amber-500" : "bg-foreground/80",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      {remainingLabel !== null && (
        <p className="mt-2 text-xs text-muted-foreground">{remainingLabel}</p>
      )}
    </div>
  );
}

function limitPct(spent: number, limit: number): number {
  if (limit <= 0) return 0;
  return Math.min(100, Math.round((spent / limit) * 100));
}

export function TokensSection() {
  const t = useT();
  const balance = useTokensStore((s) => s.balance);
  const history = useTokensStore((s) => s.history);
  const error = useTokensStore((s) => s.error);
  const phase = useTokensStore((s) => s.phase);
  const load = useTokensStore((s) => s.load);

  const translateError = React.useCallback(
    (err: unknown) => {
      if (isTokensApiError(err) && err.status === 401) return t("tokens.loginRequired");
      if (err instanceof Error && err.message) return err.message;
      return t("tokens.loadError");
    },
    [t],
  );

  // Mount / re-enter: soft refresh when cache exists (no full-page spinner).
  React.useEffect(() => {
    void load({ soft: balance !== null, errorMessage: translateError });
    // Only on mount — load identity is stable from zustand; translateError is for messages only.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only; cache prevents flicker
  }, []);

  const initialLoading = phase === "loading" && !balance;
  const refreshing = phase === "refreshing";

  if (initialLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground" data-testid="tokens-loading">
        <Loader2 className="size-4 animate-spin" /> {t("tokens.loading")}
      </div>
    );
  }

  if (error && !balance) {
    const display =
      error === "login" ? t("tokens.loginRequired") : error;
    return (
      <div className="space-y-3" data-testid="tokens-error">
        <p className="text-sm text-destructive">{display}</p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void load({ soft: false, errorMessage: translateError })}
        >
          {t("tokens.retry")}
        </Button>
      </div>
    );
  }

  if (!balance) return null;

  const dailyLeft = Math.max(0, balance.daily_limit - balance.daily_spent);
  const monthlyLeft = Math.max(0, balance.monthly_limit - balance.monthly_spent);
  const dailyPct = limitPct(balance.daily_spent, balance.daily_limit);
  const monthlyPct = limitPct(balance.monthly_spent, balance.monthly_limit);
  const byReason = balance.usage_by_reason ?? [];
  const displayError =
    error === "login" ? t("tokens.loginRequired") : error;

  return (
    <div className="space-y-8" data-testid="tokens-panel">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-medium">
            <Coins className="size-4" aria-hidden />
            {t("tokens.title")}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">{t("tokens.desc")}</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void load({ soft: true, errorMessage: translateError })}
          className="shrink-0"
          disabled={refreshing || phase === "loading"}
          data-testid="tokens-refresh"
        >
          <RefreshCw className={cn("size-3.5", refreshing && "animate-spin")} />
          {t("tokens.refresh")}
        </Button>
      </div>

      {displayError && (
        <p className="text-sm text-destructive" data-testid="tokens-soft-error">
          {displayError}
        </p>
      )}

      {(dailyPct >= 70 || monthlyPct >= 70) && (
        <div
          className={cn(
            "rounded-xl border px-4 py-3 text-sm",
            dailyPct >= 90 || monthlyPct >= 90
              ? "border-destructive/40 bg-destructive/5 text-destructive"
              : "border-amber-500/40 bg-amber-500/5 text-amber-800 dark:text-amber-200",
          )}
          data-testid="tokens-limit-warning"
          role="status"
        >
          {dailyPct >= 90 || monthlyPct >= 90
            ? t("tokens.limitCritical", {
                daily: dailyPct,
                monthly: monthlyPct,
              })
            : t("tokens.limitWarning", {
                daily: dailyPct,
                monthly: monthlyPct,
              })}
        </div>
      )}

      <section className="rounded-xl border border-border p-5">
        <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          {t("tokens.balance")}
        </p>
        <p className="mt-1 text-4xl font-semibold tabular-nums tracking-tight">
          {balance.balance}
          <span className="ml-2 text-base font-normal text-muted-foreground">
            {t("tokens.units")}
          </span>
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          {t("tokens.updated")}: {new Date(balance.updated_at).toLocaleString()}
        </p>
        <p className="mt-3 text-sm text-muted-foreground">{t("tokens.balanceHint")}</p>
        {balance.costs && (
          <p className="mt-2 text-xs text-muted-foreground" data-testid="tokens-costs">
            {t("tokens.costSchedule", {
              chat: balance.costs.chat,
              agent: balance.costs.agent,
              image: balance.costs.image,
            })}
          </p>
        )}
        <p className="mt-2 text-xs text-muted-foreground">{t("tokens.notProviderBalance")}</p>
      </section>

      <div className="grid gap-3 sm:grid-cols-2">
        <UsageBar
          label={t("tokens.dailyLimit")}
          spent={balance.daily_spent}
          limit={balance.daily_limit}
          period={balance.daily_period}
          remainingLabel={t("tokens.remainingInPeriod", {
            n: Math.max(0, balance.daily_limit - balance.daily_spent),
          })}
        />
        <UsageBar
          label={t("tokens.monthlyLimit")}
          spent={balance.monthly_spent}
          limit={balance.monthly_limit}
          period={balance.monthly_period}
          remainingLabel={t("tokens.remainingInPeriod", {
            n: Math.max(0, balance.monthly_limit - balance.monthly_spent),
          })}
        />
      </div>

      <section className="rounded-xl border border-border p-4">
        <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          {t("tokens.summary")}
        </p>
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          <div className="flex justify-between gap-2 border-b border-border/60 py-1.5">
            <dt className="text-muted-foreground">{t("tokens.dailyRemaining")}</dt>
            <dd className="font-medium tabular-nums">{dailyLeft}</dd>
          </div>
          <div className="flex justify-between gap-2 border-b border-border/60 py-1.5">
            <dt className="text-muted-foreground">{t("tokens.monthlyRemaining")}</dt>
            <dd className="font-medium tabular-nums">{monthlyLeft}</dd>
          </div>
          <div className="flex justify-between gap-2 border-b border-border/60 py-1.5 sm:col-span-2">
            <dt className="text-muted-foreground">{t("tokens.userId")}</dt>
            <dd className="truncate font-mono text-xs">{balance.user_id}</dd>
          </div>
        </dl>
      </section>

      {byReason.length > 0 && (
        <section data-testid="tokens-usage-by-reason">
          <h4 className="text-sm font-medium">{t("tokens.usageByReason")}</h4>
          <p className="mt-1 text-sm text-muted-foreground">{t("tokens.usageByReasonDesc")}</p>
          <ul className="mt-3 space-y-2">
            {byReason.map((row: UsageByReason) => (
              <li
                key={row.reason}
                className="flex items-center justify-between gap-3 rounded-lg border border-border/70 px-3 py-2 text-sm"
              >
                <span className="truncate text-muted-foreground" title={row.reason}>
                  {row.reason}
                </span>
                <span className="shrink-0 tabular-nums font-medium">
                  {row.spent}{" "}
                  <span className="text-xs font-normal text-muted-foreground">
                    ({row.count}×)
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h4 className="text-sm font-medium">{t("tokens.history")}</h4>
        <p className="mt-1 text-sm text-muted-foreground">{t("tokens.historyDesc")}</p>
        {history.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">{t("tokens.noHistory")}</p>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-xl border border-border">
            <table className="w-full min-w-[36rem] text-left text-sm">
              <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">{t("tokens.col.date")}</th>
                  <th className="px-3 py-2 font-medium">{t("tokens.col.kind")}</th>
                  <th className="px-3 py-2 font-medium">{t("tokens.col.amount")}</th>
                  <th className="px-3 py-2 font-medium">{t("tokens.col.balance")}</th>
                  <th className="px-3 py-2 font-medium">{t("tokens.col.reason")}</th>
                </tr>
              </thead>
              <tbody>
                {history.map((row) => (
                  <tr key={row.id} className="border-b border-border/70 last:border-0">
                    <td className="px-3 py-2 whitespace-nowrap text-xs text-muted-foreground">
                      {new Date(row.created_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">{kindLabel(row.kind, t)}</td>
                    <td
                      className={cn(
                        "px-3 py-2 font-medium tabular-nums",
                        row.amount < 0
                          ? "text-destructive"
                          : row.amount > 0
                            ? "text-emerald-600 dark:text-emerald-400"
                            : "",
                      )}
                    >
                      {row.amount > 0 ? `+${row.amount}` : row.amount}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {row.balance_before} → {row.balance_after}
                    </td>
                    <td
                      className="max-w-[12rem] truncate px-3 py-2 text-xs text-muted-foreground"
                      title={row.reason}
                    >
                      {row.reason}
                      {row.request_id ? (
                        <span className="mt-0.5 block truncate font-mono text-[10px]">
                          {row.request_id}
                        </span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

/**
 * Billing API client — talks only to NEXA backend.
 * Never trusts client-side "paid" flags; subscription comes from webhook → server.
 */
import { API_BASE_URL, ApiError, request } from "./api";

export type BillingInterval = "month" | "year";
export type PlanId = "free" | "starter" | "pro" | "business" | "enterprise";

export interface PlanFeature {
  id: string;
  label: string;
}

export interface PlanPublic {
  id: PlanId;
  name: string;
  tagline: string;
  currency: string;
  monthly_amount: number;
  yearly_amount: number;
  popular: boolean;
  highlight: string | null;
  cta: string;
  contact_sales: boolean;
  features: PlanFeature[];
  experiment_limit: number | null;
  yearly_savings_percent: number | null;
}

export interface BillingOverview {
  plan: PlanId;
  plan_name: string;
  status: string;
  billing_interval: BillingInterval;
  features: string[];
  experiment_limit: number | null;
  cancel_at_period_end: boolean;
  current_period_end: string | null;
  usage: {
    period: string;
    experiments_used: number;
    experiments_limit: number | null;
    experiments_remaining: number | null;
    plan: string;
  };
  provider_configured: boolean;
  provider_status?: {
    provider: string;
    configured: boolean;
    mode: string;
    currency: string;
    activation: string;
  };
  payment_methods: Array<{
    id: string;
    brand: string | null;
    last4: string | null;
    exp_month: number | null;
    exp_year: number | null;
  }>;
  invoices: Array<{
    id: string;
    amount: number;
    currency: string;
    status: string;
    invoice_url: string | null;
    created_at: string;
  }>;
  payments: Array<{
    id: string;
    amount: number;
    currency: string;
    status: string;
    description: string | null;
    created_at: string;
  }>;
}

export function formatRub(amountKopecks: number): string {
  if (amountKopecks < 0) return "Custom";
  if (amountKopecks === 0) return "0 ₽";
  const rub = Math.round(amountKopecks / 100);
  return `${rub.toLocaleString("ru-RU")} ₽`;
}

export async function fetchPlans(): Promise<{ plans: PlanPublic[]; currency: string }> {
  return request("/api/billing/plans");
}

export async function fetchBillingMe(): Promise<BillingOverview> {
  return request("/api/billing/me");
}

export async function createCheckout(input: {
  plan: PlanId;
  interval: BillingInterval;
  success_url?: string;
  cancel_url?: string;
}): Promise<{ checkout_url: string; session_id: string }> {
  return request("/api/billing/checkout", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function createPortal(return_url?: string): Promise<{ portal_url: string }> {
  return request("/api/billing/portal", {
    method: "POST",
    body: JSON.stringify({ return_url }),
  });
}

export async function cancelSubscription(): Promise<{
  plan: string;
  status: string;
  cancel_at_period_end: boolean;
  current_period_end: string | null;
}> {
  return request("/api/billing/cancel", { method: "POST", body: "{}" });
}

export async function resumeSubscription(): Promise<{
  plan: string;
  status: string;
  cancel_at_period_end: boolean;
  current_period_end: string | null;
}> {
  return request("/api/billing/resume", { method: "POST", body: "{}" });
}

export async function detachPaymentMethod(payment_method_id: string): Promise<void> {
  await request("/api/billing/payment-methods/detach", {
    method: "POST",
    body: JSON.stringify({ payment_method_id }),
  });
}

export async function checkEntitlement(feature: string): Promise<{ allowed: boolean; plan: string }> {
  return request("/api/billing/entitlements/check", {
    method: "POST",
    body: JSON.stringify({ feature }),
  });
}

export async function recordExperimentUsage(): Promise<BillingOverview["usage"]> {
  return request("/api/billing/usage/experiment", { method: "POST", body: "{}" });
}

export function isBillingApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}

export { API_BASE_URL };

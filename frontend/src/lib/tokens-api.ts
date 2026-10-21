/**
 * Internal AI credits API — balance, limits, ledger.
 * Balance is never mutated from the client; this is read-only for users.
 * These are NEXA credits, not OpenAI/Anthropic account balances.
 */
import { ApiError, request } from "./api";

export interface TokenCosts {
  chat: number;
  agent: number;
  image: number;
  default: number;
}

export interface UsageByReason {
  reason: string;
  spent: number;
  count: number;
}

export interface TokenBalance {
  user_id: string;
  balance: number;
  daily_limit: number;
  monthly_limit: number;
  daily_spent: number;
  monthly_spent: number;
  daily_period: string;
  monthly_period: string;
  updated_at: string;
  /** Fixed NEXA credit schedule (server-side estimates, not provider tokens). */
  costs?: TokenCosts;
  unit?: string;
  usage_by_reason?: UsageByReason[];
}

export interface LedgerEntry {
  id: string;
  user_id: string;
  amount: number;
  kind: string;
  reason: string;
  balance_before: number;
  balance_after: number;
  request_id: string | null;
  actor_id: string | null;
  created_at: string;
}

export interface TokenHistory {
  items: LedgerEntry[];
  limit: number;
  offset: number;
}

export function fetchTokenBalance(): Promise<TokenBalance> {
  return request<TokenBalance>("/api/v1/tokens/balance");
}

export function fetchTokenHistory(limit = 50, offset = 0): Promise<TokenHistory> {
  const q = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return request<TokenHistory>(`/api/v1/tokens/history?${q}`);
}

export function isTokensApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}

export function kindLabel(kind: string, t: (key: string) => string): string {
  const key = `tokens.kind.${kind}`;
  const label = t(key);
  return label === key ? kind : label;
}

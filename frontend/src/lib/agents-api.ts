import { request } from "./api";

export interface AgentCatalogItem {
  id: string;
  name: string;
  category: string;
  category_name: string;
  description: string;
  execution_profile: string;
  status: "catalog";
  capabilities: string[];
}

export interface AgentCatalogResponse {
  agents: AgentCatalogItem[];
  count: number;
  total: number;
  categories: [string, string][];
}

export function fetchAgentCatalog(q = "", category = "", signal?: AbortSignal) {
  const params = new URLSearchParams();
  if (q.trim()) params.set("q", q.trim());
  if (category) params.set("category", category);
  const encoded = params.toString();
  const suffix = encoded ? `?${encoded}` : "";
  return request<AgentCatalogResponse>(`/api/v1/agents/catalog${suffix}`, { signal });
}

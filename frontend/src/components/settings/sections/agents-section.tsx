"use client";

import * as React from "react";
import { Bot, Loader2, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n";
import { fetchAgentCatalog, type AgentCatalogItem } from "@/lib/agents-api";

export function AgentsSection() {
  const t = useT();
  const [agents, setAgents] = React.useState<AgentCatalogItem[]>([]);
  const [count, setCount] = React.useState(0);
  const [total, setTotal] = React.useState(100);
  const [categories, setCategories] = React.useState<[string, string][]>([]);
  const [category, setCategory] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    void fetchAgentCatalog(query, category, controller.signal)
      .then((result) => {
        setAgents(result.agents);
        setCount(result.count);
        setTotal(result.total);
        setCategories(result.categories);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : t("agents.loadError"));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [query, category, t]);

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-semibold">{t("agents.title")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("agents.description")}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("agents.search")} className="pl-8" />
        </div>
        <select value={category} onChange={(e) => setCategory(e.target.value)} className="h-10 rounded-lg border border-input bg-transparent px-2.5 text-sm">
          <option value="">{t("agents.allCategories")}</option>
          {categories.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <span className="text-xs text-muted-foreground">{count} / {total}</span>
      </div>
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />{t("agents.loading")}</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {agents.map((agent) => (
            <article key={agent.id} className="rounded-xl border border-border/70 p-3">
              <div className="flex items-start gap-2">
                <div className="rounded-lg bg-muted p-2"><Bot className="size-4" aria-hidden="true" /></div>
                <div className="min-w-0 flex-1">
                  <h4 className="text-sm font-semibold">{agent.name}</h4>
                  <p className="text-xs text-muted-foreground">{agent.category_name}</p>
                </div>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{agent.description}</p>
              <p className="mt-3 text-[11px] text-muted-foreground">{t("agents.catalogRole")}</p>
            </article>
          ))}
          {agents.length === 0 && <p className="text-sm text-muted-foreground">{t("agents.empty")}</p>}
        </div>
      )}
      <p className="text-xs text-muted-foreground">{t("agents.runtimeNote")}</p>
    </div>
  );
}

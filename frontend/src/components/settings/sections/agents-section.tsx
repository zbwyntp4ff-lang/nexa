"use client";

import * as React from "react";
import { Bot, Loader2, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { fetchAgentCatalog, runSpecialistAgent, type AgentCatalogItem } from "@/lib/agents-api";

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
  const [task, setTask] = React.useState("");
  const [runningAgent, setRunningAgent] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<{ name: string; answer: string; model: string | null } | null>(null);

  async function runAgent(agent: AgentCatalogItem) {
    if (!task.trim()) return;
    setRunningAgent(agent.id);
    setError(null);
    setResult(null);
    try {
      const response = await runSpecialistAgent(agent.id, task.trim());
      setResult({ name: agent.name, answer: response.final_answer ?? t("agents.noAnswer"), model: response.model });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("agents.runError"));
    } finally {
      setRunningAgent(null);
    }
  }

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
      <div className="space-y-2 rounded-xl border border-border/70 p-3">
        <label className="block text-sm font-medium" htmlFor="agent-task">{t("agents.taskLabel")}</label>
        <textarea id="agent-task" value={task} onChange={(e) => setTask(e.target.value)} rows={3} maxLength={12000} placeholder={t("agents.taskPlaceholder")} className="w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm" />
        <p className="text-xs text-muted-foreground">{t("agents.runHint")}</p>
      </div>
      {result && <div className="space-y-2 rounded-xl border border-border/70 p-3"><p className="text-sm font-semibold">{t("agents.resultFrom", { name: result.name })}</p><p className="whitespace-pre-wrap text-sm">{result.answer}</p>{result.model && <p className="text-xs text-muted-foreground">{result.model}</p>}</div>}
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
              <div className="mt-3 flex items-center justify-between gap-2"><p className="text-[11px] text-muted-foreground">{t("agents.catalogRole")}</p><Button size="sm" variant="outline" disabled={!task.trim() || runningAgent !== null} onClick={() => void runAgent(agent)}>{runningAgent === agent.id ? t("agents.running") : t("agents.run")}</Button></div>
            </article>
          ))}
          {agents.length === 0 && <p className="text-sm text-muted-foreground">{t("agents.empty")}</p>}
        </div>
      )}
      <p className="text-xs text-muted-foreground">{t("agents.runtimeNote")}</p>
    </div>
  );
}

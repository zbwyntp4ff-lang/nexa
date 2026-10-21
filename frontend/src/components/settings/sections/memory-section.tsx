"use client";
import * as React from "react";
import { Loader2, Search, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { ApiError, createMemory, deleteMemory, listMemory, type MemoryItemApi } from "@/lib/api";
import { useT } from "@/lib/i18n";
const MEMORY_TYPES = ["short_term", "conversation", "long_term", "user_preference"] as const;
export function MemorySection() {
  const t = useT();
  const [items, setItems] = React.useState<MemoryItemApi[]>([]);
  const [query, setQuery] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [newContent, setNewContent] = React.useState("");
  const [newType, setNewType] = React.useState<(typeof MEMORY_TYPES)[number]>("long_term");
  const [saving, setSaving] = React.useState(false);
  const [contradiction, setContradiction] = React.useState<{
    existing_id: string;
    existing_content: string;
    reason: string;
  } | null>(null);
  const load = React.useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await listMemory({ query: q, limit: 50 });
      setItems(response.results.map((r) => r.item));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the NEXA backend.");
    } finally {
      setLoading(false);
    }
  }, []);
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load("");
  }, [load]);
  async function handleAdd(opts?: { force?: boolean; replace_id?: string }) {
    if (!newContent.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const result = await createMemory({
        content: newContent.trim(),
        type: newType,
        force: opts?.force,
        replace_id: opts?.replace_id,
      });
      if (!result.saved && result.contradictions.length > 0) {
        const first = result.contradictions[0];
        setContradiction({
          existing_id: first.existing_id,
          existing_content: first.existing_content,
          reason: first.reason,
        });
        return;
      }
      setContradiction(null);
      setNewContent("");
      await load(query);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this memory item.");
    } finally {
      setSaving(false);
    }
  }
  async function handleDelete(id: string) {
    try {
      await deleteMemory(id);
      setItems((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete this memory item.");
    }
  }
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium">{t("memory.title")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("memory.desc")}</p>
      </div>
      <div className="flex gap-2">
        <Select value={newType} onValueChange={(v) => setNewType(v as typeof newType)}>
          <SelectTrigger className="w-40" aria-label={t("memory.type")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {MEMORY_TYPES.map((type) => (
              <SelectItem key={type} value={type}>{t(`memory.${type.replace("_", "")}`)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          placeholder={t("memory.placeholder")}
          aria-label={t("memory.newContent")}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
        />
        <Button onClick={() => void handleAdd()} disabled={saving || !newContent.trim()}>
          {saving ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : t("memory.save")}
        </Button>
      </div>
      {contradiction && (
        <div className="space-y-2 rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
          <p className="font-medium">{t("memory.contradictionTitle")}</p>
          <p className="text-xs text-muted-foreground">{contradiction.reason}</p>
          <p className="text-xs">{t("memory.contradictionExisting")}: {contradiction.existing_content}</p>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={saving}
              onClick={() => void handleAdd({ replace_id: contradiction.existing_id })}
            >
              {t("memory.replaceOld")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={saving}
              onClick={() => void handleAdd({ force: true })}
            >
              {t("memory.keepBoth")}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setContradiction(null)}>
              {t("memory.cancel")}
            </Button>
          </div>
        </div>
      )}
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input
          value={query}
          onChange={(e) => { setQuery(e.target.value); void load(e.target.value); }}
          placeholder={t("memory.searchPlaceholder")}
          aria-label={t("memory.searchMemory")}
          className="pl-8"
        />
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" /> {t("memory.loading")}
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("memory.noItems")}</p>
      ) : (
        <ul className="max-h-64 space-y-1.5 overflow-y-auto nexa-scrollbar">
          {items.map((item) => (
            <li key={item.id} className="flex items-start justify-between gap-2 rounded-lg border border-border p-2.5 text-sm">
              <div className="min-w-0">
                <p className="truncate">{item.content}</p>
                <span className="text-xs text-muted-foreground">{t(`memory.${item.type.replace("_", "")}`)}</span>
              </div>
              <button
                type="button"
                onClick={() => handleDelete(item.id)}
                aria-label={`${t("chat.remove")}: ${item.content}`}
                className="shrink-0 rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Trash2 className="size-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

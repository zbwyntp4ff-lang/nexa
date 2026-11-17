"use client";
import * as React from "react";
import { Loader2, Search, Trash2, Pencil, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  ApiError, clearMemory, createMemory, deleteMemory, listMemory, updateMemory,
  type MemoryItemApi,
} from "@/lib/api";
import { useT } from "@/lib/i18n";

const MEMORY_TYPES = ["short_term", "conversation", "long_term", "user_preference"] as const;

export function MemorySection() {
  const t = useT();
  const [items, setItems] = React.useState<MemoryItemApi[]>([]);
  const [query, setQuery] = React.useState("");
  const [filterType, setFilterType] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [newContent, setNewContent] = React.useState("");
  const [newType, setNewType] = React.useState<(typeof MEMORY_TYPES)[number]>("long_term");
  const [saving, setSaving] = React.useState(false);
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [editingContent, setEditingContent] = React.useState("");
  const [editBusy, setEditBusy] = React.useState(false);
  const [clearBusy, setClearBusy] = React.useState(false);
  const [contradiction, setContradiction] = React.useState<{
    existing_id: string;
    existing_content: string;
    reason: string;
  } | null>(null);

  const load = React.useCallback(async (q: string, type: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await listMemory({ query: q, type: type || undefined, limit: 100 });
      setItems(response.results.map((r) => r.item));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the NEXA backend.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load(query, filterType);
  }, [load, query, filterType]);

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
      await load(query, filterType);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this memory item.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveEdit(item: MemoryItemApi) {
    if (!editingContent.trim()) return;
    setEditBusy(true);
    setError(null);
    try {
      const updated = await updateMemory(item.id, { content: editingContent.trim() });
      setItems((prev) => prev.map((entry) => entry.id === updated.id ? updated : entry));
      setEditingId(null);
      setEditingContent("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update this memory item.");
    } finally {
      setEditBusy(false);
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

  async function handleClearAll() {
    setClearBusy(true);
    setError(null);
    try {
      await clearMemory();
      setItems([]);
      setEditingId(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not clear memory.");
    } finally {
      setClearBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium">{t("memory.title")}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{t("memory.desc")}</p>
        </div>
        <AlertDialog>
          <AlertDialogTrigger render={<Button type="button" size="sm" variant="outline" className="text-destructive hover:text-destructive" disabled={clearBusy}>{t("memory.clearAll")}</Button>} />
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t("memory.clearConfirmTitle")}</AlertDialogTitle>
              <AlertDialogDescription>{t("memory.clearConfirmDesc")}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t("chat.cancel")}</AlertDialogCancel>
              <AlertDialogAction disabled={clearBusy} onClick={() => void handleClearAll()}>{clearBusy ? <Loader2 className="size-4 animate-spin" /> : t("memory.clearAll")}</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <Select value={newType} onValueChange={(v) => setNewType(v as typeof newType)}>
          <SelectTrigger className="w-full sm:w-40" aria-label={t("memory.type")}><SelectValue /></SelectTrigger>
          <SelectContent>
            {MEMORY_TYPES.map((type) => <SelectItem key={type} value={type}>{t(`memory.${type.replace("_", "")}`)}</SelectItem>)}
          </SelectContent>
        </Select>
        <Input value={newContent} onChange={(e) => setNewContent(e.target.value)} placeholder={t("memory.placeholder")} aria-label={t("memory.newContent")} onKeyDown={(e) => e.key === "Enter" && void handleAdd()} />
        <Button onClick={() => void handleAdd()} disabled={saving || !newContent.trim()}>{saving ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : t("memory.save")}</Button>
      </div>

      {contradiction && (
        <div className="space-y-2 rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
          <p className="font-medium">{t("memory.contradictionTitle")}</p>
          <p className="text-xs text-muted-foreground">{contradiction.reason}</p>
          <p className="text-xs">{t("memory.contradictionExisting")}: {contradiction.existing_content}</p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" disabled={saving} onClick={() => void handleAdd({ replace_id: contradiction.existing_id })}>{t("memory.replaceOld")}</Button>
            <Button type="button" size="sm" variant="outline" disabled={saving} onClick={() => void handleAdd({ force: true })}>{t("memory.keepBoth")}</Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setContradiction(null)}>{t("memory.cancel")}</Button>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("memory.searchPlaceholder")} aria-label={t("memory.searchMemory")} className="pl-8" />
        </div>
        <Select value={filterType || "all"} onValueChange={(v) => setFilterType(!v || v === "all" ? "" : v)}>
          <SelectTrigger className="w-full sm:w-48" aria-label={t("memory.filterType")}><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("memory.allTypes")}</SelectItem>
            {MEMORY_TYPES.map((type) => <SelectItem key={type} value={type}>{t(`memory.${type.replace("_", "")}`)}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" aria-hidden="true" /> {t("memory.loading")}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("memory.noItems")}</p>
      ) : (
        <ul className="max-h-96 space-y-1.5 overflow-y-auto nexa-scrollbar">
          {items.map((item) => (
            <li key={item.id} className="rounded-lg border border-border p-2.5 text-sm">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  {editingId === item.id ? (
                    <Input autoFocus value={editingContent} onChange={(e) => setEditingContent(e.target.value)} maxLength={2000} aria-label={t("memory.editContent")} />
                  ) : (
                    <p className="whitespace-pre-wrap break-words">{item.content}</p>
                  )}
                  <span className="mt-1 block text-xs text-muted-foreground">{t(`memory.${item.type.replace("_", "")}`)} · {new Date(item.updated_at).toLocaleDateString()}</span>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  {editingId === item.id ? (
                    <>
                      <Button type="button" size="icon-sm" variant="ghost" disabled={editBusy || !editingContent.trim()} aria-label={t("memory.saveEdit")} onClick={() => void handleSaveEdit(item)}><Check className="size-4" /></Button>
                      <Button type="button" size="icon-sm" variant="ghost" disabled={editBusy} aria-label={t("memory.cancelEdit")} onClick={() => setEditingId(null)}><X className="size-4" /></Button>
                    </>
                  ) : (
                    <Button type="button" size="icon-sm" variant="ghost" aria-label={t("memory.edit")} onClick={() => { setEditingId(item.id); setEditingContent(item.content); }}><Pencil className="size-4" /></Button>
                  )}
                  <Button type="button" size="icon-sm" variant="ghost" aria-label={`${t("chat.remove")}: ${item.content}`} onClick={() => void handleDelete(item.id)}><Trash2 className="size-4" /></Button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

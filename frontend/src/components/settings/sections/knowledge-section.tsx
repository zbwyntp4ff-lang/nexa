"use client";
import * as React from "react";
import { AlertCircle, CheckCircle2, FileText, Loader2, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  addKnowledgeNote,
  deleteKnowledgeDocument,
  listKnowledgeDocuments,
  uploadKnowledgeDocument,
  type KnowledgeDocumentApi,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatFileSize } from "@/lib/attachments";
export function KnowledgeSection() {
  const t = useT();
  const [documents, setDocuments] = React.useState<KnowledgeDocumentApi[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [noteTitle, setNoteTitle] = React.useState("");
  const [noteText, setNoteText] = React.useState("");
  const [savingNote, setSavingNote] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDocuments(await listKnowledgeDocuments());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the NEXA backend.");
    } finally {
      setLoading(false);
    }
  }, []);
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);
  async function handleFileSelected(file: File) {
    setUploading(true);
    setError(null);
    try {
      const doc = await uploadKnowledgeDocument(file);
      setDocuments((prev) => [doc, ...prev]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not index this document.");
    } finally {
      setUploading(false);
    }
  }
  async function handleAddNote() {
    if (!noteTitle.trim() || !noteText.trim()) return;
    setSavingNote(true);
    setError(null);
    try {
      const doc = await addKnowledgeNote(noteTitle.trim(), noteText.trim());
      setDocuments((prev) => [doc, ...prev]);
      setNoteTitle("");
      setNoteText("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this note.");
    } finally {
      setSavingNote(false);
    }
  }
  async function handleDelete(id: string) {
    try {
      await deleteKnowledgeDocument(id);
      setDocuments((prev) => prev.filter((doc) => doc.id !== id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete this document.");
    }
  }
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium">{t("knowledge.title")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("knowledge.desc")}</p>
      </div>
      <div className="flex gap-2">
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFileSelected(file);
            e.target.value = "";
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={uploading}
          onClick={() => fileInputRef.current?.click()}
        >
          {uploading ? (
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <Plus className="size-4" aria-hidden="true" />
          )}
          {t("knowledge.addDocument")}
        </Button>
      </div>
      <div className="space-y-2 rounded-lg border border-border p-3">
        <p className="text-sm font-medium">{t("knowledge.addNote")}</p>
        <Input
          value={noteTitle}
          onChange={(e) => setNoteTitle(e.target.value)}
          placeholder={t("knowledge.notePlaceholder")}
          aria-label={t("knowledge.notePlaceholder")}
        />
        <Textarea
          value={noteText}
          onChange={(e) => setNoteText(e.target.value)}
          placeholder={t("knowledge.noteTextPlaceholder")}
          aria-label={t("knowledge.noteTextPlaceholder")}
          rows={2}
        />
        <Button size="sm" onClick={handleAddNote} disabled={savingNote || !noteTitle.trim() || !noteText.trim()}>
          {savingNote ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : t("knowledge.save")}
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" /> {t("knowledge.loading")}
        </p>
      ) : documents.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("knowledge.empty")}</p>
      ) : (
        <ul className="max-h-64 space-y-1.5 overflow-y-auto nexa-scrollbar">
          {documents.map((doc) => (
            <li
              key={doc.id}
              className="flex items-start justify-between gap-2 rounded-lg border border-border p-2.5 text-sm"
            >
              <div className="flex min-w-0 items-start gap-2">
                <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <div className="min-w-0">
                  <p className="truncate font-medium">{doc.filename}</p>
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    {doc.status === "ready" && (
                      <>
                        <CheckCircle2 className="size-3 text-success" aria-hidden="true" />
                        {t("knowledge.statusReady")} · {doc.chunk_count} {t("knowledge.chunks")}
                      </>
                    )}
                    {doc.status === "processing" && (
                      <>
                        <Loader2 className="size-3 animate-spin" aria-hidden="true" />
                        {t("knowledge.statusProcessing")}
                      </>
                    )}
                    {doc.status === "error" && (
                      <>
                        <AlertCircle className="size-3 text-destructive" aria-hidden="true" />
                        {t("knowledge.statusError")}
                        {doc.error ? `: ${doc.error}` : ""}
                      </>
                    )}
                    {" · "}
                    {t(`knowledge.source.${doc.source_type}`)}
                    {doc.size_bytes > 0 ? ` · ${formatFileSize(doc.size_bytes)}` : ""}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleDelete(doc.id)}
                aria-label={`${t("knowledge.remove")}: ${doc.filename}`}
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

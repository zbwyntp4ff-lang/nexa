"use client";
import * as React from "react";
import { AlertCircle, ArrowUp, FileText, ImagePlus, Loader2, Mic, Paperclip, Square, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { MODE_GLOW, MODE_GRADIENT } from "@/lib/mode-theme";
import { usePluginsStore } from "@/store/plugins-store";
import { useUiStore } from "@/store/ui-store";
import { ModelQuickSwitch } from "./model-quick-switch";
import {
  DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE,
  DEFAULT_MAX_ATTACHMENT_SIZE_BYTES,
  createLocalAttachment,
  deleteAttachmentBestEffort,
  formatFileSize,
  safeRevokeObjectUrl,
  uploadAttachment,
  validateLocalFile,
} from "@/lib/attachments";
import type { AppMode, AttachmentView } from "@/lib/types";
interface ComposerProps {
  mode?: AppMode;
  onSend: (text: string, attachments?: AttachmentView[]) => void;
  onStop: () => void;
  isSending: boolean;
  disabled?: boolean;
  placeholder?: string;
}
export function Composer({ mode = "chat", onSend, onStop, isSending, disabled, placeholder }: ComposerProps) {
  const t = useT();
  const isPublicBeta = process.env.NEXT_PUBLIC_NEXA_PUBLIC_BETA === "true";
  const visionEnabled = usePluginsStore((s) => s.enabled.vision);
  const enterToSend = useUiStore((s) => s.enterToSend);
  const [value, setValue] = React.useState("");
  const [attachments, setAttachments] = React.useState<AttachmentView[]>([]);
  const [isDragging, setIsDragging] = React.useState(false);
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const imageInputRef = React.useRef<HTMLInputElement | null>(null);
  const dragCounter = React.useRef(0);
  function resizeTextarea() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }
  React.useEffect(resizeTextarea, [value]);
  React.useEffect(() => {
    return () => {
      for (const attachment of attachments) safeRevokeObjectUrl(attachment.previewUrl);
    };
    // Only run on unmount - intentionally not re-running per attachment change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  function updateAttachment(id: string, patch: Partial<AttachmentView>) {
    setAttachments((prev) => prev.map((a) => (a.id === id ? { ...a, ...patch } : a)));
  }
  async function addFiles(files: FileList | File[]) {
    if (isPublicBeta) return;
    const list = Array.from(files);
    if (list.length === 0) return;
    const availableSlots = DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE - attachments.length;
    if (availableSlots <= 0) {
      toast(t("chat.tooManyAttachments", { max: DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE }));
      return;
    }
    const toAdd = list.slice(0, availableSlots);
    if (toAdd.length < list.length) {
      toast(t("chat.tooManyAttachments", { max: DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE }));
    }
    for (const file of toAdd) {
      const local = createLocalAttachment(file);
      const validationError = validateLocalFile(file, DEFAULT_MAX_ATTACHMENT_SIZE_BYTES);
      if (validationError) {
        setAttachments((prev) => [...prev, { ...local, status: "failed", error: validationError }]);
        continue;
      }
      setAttachments((prev) => [...prev, local]);
      uploadAttachment(file, (percent) => updateAttachment(local.id, { progress: percent })).then((outcome) => {
        updateAttachment(local.id, {
          status: outcome.status,
          error: outcome.error,
          serverId: outcome.status === "ready" ? outcome.id : undefined,
          charCount: outcome.charCount,
          pageCount: outcome.pageCount,
          progress: 100,
        });
      });
    }
  }
  function removeAttachment(id: string) {
    setAttachments((prev) => {
      const target = prev.find((a) => a.id === id);
      safeRevokeObjectUrl(target?.previewUrl);
      if (target?.serverId) deleteAttachmentBestEffort(target.serverId);
      return prev.filter((a) => a.id !== id);
    });
  }
  function handleSubmit() {
    if (disabled || isSending) return;
    if (!value.trim() && attachments.length === 0) return;
    if (attachments.some((a) => a.status === "uploading" || a.status === "processing")) {
      toast(t("chat.attachmentsStillUploading"));
      return;
    }
    onSend(value, attachments.length > 0 ? attachments : undefined);
    for (const attachment of attachments) safeRevokeObjectUrl(attachment.previewUrl);
    setValue("");
    setAttachments([]);
  }
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((enterToSend && e.key === "Enter" && !e.shiftKey) || (!enterToSend && e.key === "Enter" && (e.metaKey || e.ctrlKey))) {
      e.preventDefault();
      handleSubmit();
    }
  }
  function handleVoiceClick() {
    useUiStore.getState().setActiveView("hexa");
  }
  const hasPendingAttachments = attachments.some((a) => a.status === "uploading" || a.status === "processing");
  return (
    <div
      className={cn("border-t border-border/40 bg-transparent p-3 sm:p-4", isDragging && "bg-accent/20")}
      onDragEnter={(e) => {
        if (isPublicBeta) return;
        e.preventDefault(); dragCounter.current += 1; setIsDragging(true);
      }}
      onDragOver={(e) => { if (!isPublicBeta) e.preventDefault(); }}
      onDragLeave={() => {
        if (isPublicBeta) return;
        dragCounter.current -= 1; if (dragCounter.current <= 0) setIsDragging(false);
      }}
      onDrop={(e) => {
        e.preventDefault(); dragCounter.current = 0; setIsDragging(false);
        if (!isPublicBeta && e.dataTransfer.files?.length) void addFiles(e.dataTransfer.files);
      }}
    >
      <div className={cn("nexa-glass mx-auto flex max-w-3xl flex-col gap-2 rounded-3xl p-2.5 transition-colors", isDragging && "border-primary border-dashed")}>
        {isDragging && <p className="px-2 pt-1 text-center text-xs font-medium text-primary">{t("chat.dropFiles")}</p>}
        {attachments.length > 0 && (
          <ul className="flex flex-wrap gap-1.5 px-1" aria-label={t("chat.attachments")}>
            {attachments.map((attachment) => (
              <li
                key={attachment.id}
                className={cn(
                  "flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs",
                  attachment.status === "failed" && "bg-destructive/10 text-destructive"
                )}
              >
                {attachment.previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={attachment.previewUrl} alt="" className="size-4 rounded-sm object-cover" />
                ) : attachment.kind === "image" ? (
                  <ImagePlus className="size-3" aria-hidden="true" />
                ) : (
                  <FileText className="size-3" aria-hidden="true" />
                )}
                <span className="max-w-40 truncate">{attachment.name}</span>
                {attachment.status === "uploading" ? (
                  <span className="flex items-center gap-1 text-muted-foreground">
                    <Loader2 className="size-3 animate-spin" aria-hidden="true" />
                    {attachment.progress}%
                  </span>
                ) : attachment.status === "processing" ? (
                  <span className="flex items-center gap-1 text-muted-foreground">
                    <Loader2 className="size-3 animate-spin" aria-hidden="true" />
                    {t("chat.processing")}
                  </span>
                ) : attachment.status === "failed" ? (
                  <Tooltip>
                    <TooltipTrigger render={<span className="flex items-center gap-1"><AlertCircle className="size-3" aria-hidden="true" />{t("chat.uploadFailed")}</span>} />
                    <TooltipContent>{attachment.error ?? t("chat.uploadFailed")}</TooltipContent>
                  </Tooltip>
                ) : (
                  <span className="text-muted-foreground">{formatFileSize(attachment.size)}</span>
                )}
                <button
                  type="button"
                  onClick={() => removeAttachment(attachment.id)}
                  aria-label={`${t("chat.remove")} ${attachment.name}`}
                  className="rounded-full p-0.5 hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <X className="size-3" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <Textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder ?? t("chat.askPlaceholder")}
          disabled={disabled}
          rows={1}
          aria-label={t("chat.messageNexa")}
          className="max-h-[200px] min-h-10 resize-none border-none bg-transparent px-2 shadow-none focus-visible:ring-0 dark:bg-transparent"
        />
        <div className="flex items-center justify-between px-1">
          <div className={cn("flex items-center gap-1", isPublicBeta && "hidden")}>
            <input ref={fileInputRef} type="file" multiple className="hidden" onChange={(e) => { if (e.target.files) void addFiles(e.target.files); e.target.value = ""; }} />
            <input ref={imageInputRef} type="file" accept="image/*" multiple className="hidden" onChange={(e) => { if (e.target.files) void addFiles(e.target.files); e.target.value = ""; }} />
            <Tooltip>
              <TooltipTrigger render={<Button type="button" variant="ghost" size="icon" aria-label={t("chat.attachFile")} onClick={() => fileInputRef.current?.click()}><Paperclip className="size-4" aria-hidden="true" /></Button>} />
              <TooltipContent>{t("chat.attachFile")}</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={t("chat.attachImage")}
                    disabled={!visionEnabled}
                    onClick={() => imageInputRef.current?.click()}
                  >
                    <ImagePlus className="size-4" aria-hidden="true" />
                  </Button>
                }
              />
              <TooltipContent>{visionEnabled ? t("chat.attachImage") : t("plugins.visionDisabledHint")}</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger render={<Button type="button" variant="ghost" size="icon" aria-label={t("chat.voiceInput")} onClick={handleVoiceClick}><Mic className="size-4" aria-hidden="true" /></Button>} />
              <TooltipContent>{t("chat.voiceInput")}</TooltipContent>
            </Tooltip>
          </div>
          <div className="flex items-center gap-1">
            {!isPublicBeta && <ModelQuickSwitch />
            {isSending ? (
              <Button type="button" size="icon" variant="secondary" aria-label={t("chat.stopGenerating")} onClick={onStop}>
                <Square className="size-4" aria-hidden="true" />
              </Button>
            ) : (
              <Button
                type="button"
                size="icon"
                aria-label={t("chat.send")}
                disabled={disabled || hasPendingAttachments || (!value.trim() && attachments.length === 0)}
                onClick={handleSubmit}
                className={cn(
                  MODE_GRADIENT[mode],
                  "border-none text-white transition-opacity duration-200 hover:opacity-90",
                  MODE_GLOW[mode]
                )}
              >
                <ArrowUp className="size-4" aria-hidden="true" />
              </Button>
            )}
          </div>
        </div>
      </div>
      <p className="mx-auto mt-1.5 max-w-3xl text-center text-[11px] text-muted-foreground">{t("chat.disclaimer")}</p>
    </div>
  );
}

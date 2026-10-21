"use client";
import * as React from "react";
import { AlertCircle, ExternalLink, FileText, ImageIcon, Loader2 } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { LogoMark } from "@/components/common/logo";
import { MarkdownMessage } from "./markdown-message";
import { MessageActions } from "./message-actions";
import { ToolResultList } from "./tool-result";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { MODE_GRADIENT } from "@/lib/mode-theme";
import type { ChatMessageView } from "@/lib/types";
export function Message({
  message, onRetry, onEdit, onStop, userRequest,
}: {
  message: ChatMessageView;
  onRetry: () => void;
  onEdit: (newContent: string) => void;
  onStop: () => void;
  /** Prior user turn — used only for optional answer feedback. */
  userRequest?: string;
}) {
  const t = useT();
  const [isEditing, setIsEditing] = React.useState(false);
  const [draft, setDraft] = React.useState(message.content);
  const isUser = message.role === "user";
  function commitEdit() {
    setIsEditing(false);
    if (draft.trim() && draft.trim() !== message.content) onEdit(draft.trim());
  }
  return (
    <div className={cn("group flex gap-3 px-4 py-4 sm:px-6", isUser ? "flex-row-reverse" : "flex-row")} data-role={message.role}>
      <Avatar className="mt-0.5 size-7 shrink-0">
        {isUser ? (
          <AvatarFallback className="bg-secondary text-secondary-foreground text-xs">{t("chat.you").slice(0, 2)}</AvatarFallback>
        ) : (
          <AvatarFallback className={cn(MODE_GRADIENT[message.mode], "overflow-hidden p-0 text-white")}>
            <LogoMark className="size-full rounded-full" />
          </AvatarFallback>
        )}
      </Avatar>
      <div className={cn("flex min-w-0 max-w-[85%] flex-col gap-1", isUser ? "items-end" : "items-start")}>
        <span className="text-xs font-medium text-muted-foreground">{isUser ? t("chat.you") : t("chat.emptyTitle")}</span>
        {!isUser && message.modelLabel && (
          <span className="text-[11px] text-muted-foreground">{t("chat.answeredBy", { model: message.modelLabel })}</span>
        )}
        {!isUser && (message.routing?.taskKind || message.latency?.totalMs != null) && (
          <span className="font-mono text-[10px] text-muted-foreground/80">
            {message.routing?.selectionMode === "auto" && message.routing.taskKind
              ? `auto · ${message.routing.taskKind}`
              : message.routing?.selectionMode === "manual"
                ? "manual"
                : null}
            {message.latency?.totalMs != null && (
              <>
                {(message.routing?.selectionMode || message.routing?.taskKind) ? " · " : null}
                {Math.round(message.latency.totalMs)}ms
              </>
            )}
            {message.routing?.promptTokens != null && message.routing?.completionTokens != null && (
              <> · {message.routing.promptTokens}↑ {message.routing.completionTokens}↓ tok</>
            )}
          </span>
        )}
        {isEditing ? (
          <div className="w-full min-w-[16rem] space-y-2">
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
              rows={3}
              aria-label={t("chat.editMessage")}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); commitEdit(); }
                if (e.key === "Escape") setIsEditing(false);
              }}
            />
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setIsEditing(false)}>{t("chat.cancel")}</Button>
              <Button size="sm" onClick={commitEdit}>{t("chat.saveSubmit")}</Button>
            </div>
          </div>
        ) : (
          <div className={cn("min-w-0 rounded-2xl px-4 py-2.5 break-words", isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground")}>
            {message.attachments && message.attachments.length > 0 && (
              <ul className="mb-2 flex flex-wrap gap-1.5" aria-label={t("chat.attachments")}>
                {message.attachments.map((attachment) => (
                  <li
                    key={attachment.id}
                    className={cn(
                      "flex items-center gap-1 rounded-full px-2 py-0.5 text-xs",
                      isUser ? "bg-primary-foreground/15" : "bg-background/60",
                      attachment.status === "failed" && "opacity-60 line-through"
                    )}
                  >
                    {attachment.kind === "image" ? (
                      <ImageIcon className="size-3" aria-hidden="true" />
                    ) : (
                      <FileText className="size-3" aria-hidden="true" />
                    )}
                    {attachment.name}
                  </li>
                ))}
              </ul>
            )}
            {message.pending && message.content ? (
              <>
                {isUser ? (
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                ) : (
                  <MarkdownMessage content={message.content} />
                )}
                <span className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />{" "}
                  {message.progressLabel || t("chat.typing")}
                </span>
              </>
            ) : null}
            {message.pending && !message.content && (
              <span className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />{" "}
                {message.progressLabel || t("chat.thinking")}
              </span>
            )}
            {message.error && (
              <span className="flex items-start gap-2 text-sm text-destructive">
                <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" /> {message.error}
              </span>
            )}
            {!message.pending && !message.error && (
              <>
                {message.agentSteps && <ToolResultList steps={message.agentSteps} />}
                {isUser ? (
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                ) : (
                  <MarkdownMessage content={message.content} />
                )}
                {message.generatedImages && message.generatedImages.length > 0 && (
                  <ul className="mt-2 flex flex-wrap gap-2" aria-label={t("chat.generatedImages")}>
                    {message.generatedImages.map((img, i) => (
                      <li key={i}>
                        <img
                          src={img.format === "b64_json" ? `data:image/png;base64,${img.base64}` : img.url}
                          alt={t("chat.generatedImageAlt", { index: String(i + 1) })}
                          className="max-h-80 max-w-full rounded-lg border border-border/60"
                        />
                      </li>
                    ))}
                  </ul>
                )}
                {message.generatedVideos && message.generatedVideos.length > 0 && (
                  <ul className="mt-2 flex flex-col gap-2" aria-label={t("chat.generatedVideos")}>
                    {message.generatedVideos.map((vid, i) => (
                      <li key={i} className="max-w-xl">
                        <video
                          src={vid.url}
                          controls
                          playsInline
                          className="w-full rounded-lg border border-border/60 bg-black"
                          aria-label={t("chat.generatedVideoAlt", { index: String(i + 1) })}
                        />
                      </li>
                    ))}
                  </ul>
                )}
                {message.citations && message.citations.length > 0 && (
                  <ol className="mt-2 flex flex-col gap-1 border-t border-border/60 pt-2 text-xs" aria-label={t("chat.sources")}>
                    {message.citations.map((c) => {
                      const external = c.url.startsWith("http://") || c.url.startsWith("https://");
                      return (
                        <li key={c.index} className="flex items-start gap-1.5 text-muted-foreground">
                          <span className="shrink-0 font-medium">[{c.index}]</span>
                          {external ? (
                            <a
                              href={c.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex min-w-0 items-center gap-1 truncate hover:text-foreground hover:underline"
                            >
                              <span className="truncate">{c.title || c.url}</span>
                              <ExternalLink className="size-3 shrink-0" aria-hidden="true" />
                            </a>
                          ) : (
                            <span className="truncate" title={c.url}>
                              {c.title || c.url}
                            </span>
                          )}
                        </li>
                      );
                    })}
                  </ol>
                )}
              </>
            )}
          </div>
        )}
        {!isEditing && (
          <MessageActions
            content={message.content}
            userRequest={!isUser ? userRequest : undefined}
            messageId={message.id}
            canEdit={isUser}
            canRegenerate={!isUser && !message.pending}
            regenerateLabel={message.error ? t("chat.retry") : t("chat.regenerate")}
            isPending={message.pending}
            onEdit={() => { setDraft(message.content); setIsEditing(true); }}
            onRegenerate={onRetry}
            onStop={onStop}
            className="opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
          />
        )}
      </div>
    </div>
  );
}

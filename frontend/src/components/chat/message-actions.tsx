"use client";
import * as React from "react";
import { Check, Copy, Pencil, RefreshCw, Square, ThumbsDown, ThumbsUp } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import {
  submitAnswerFeedback,
  type FeedbackRating,
} from "@/lib/learning-api";

function ActionButton({
  label,
  onClick,
  children,
  active,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
  active?: boolean;
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <button
            type="button"
            onClick={onClick}
            aria-label={label}
            className={cn(
              "rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active && "bg-muted text-foreground",
            )}
          >
            {children}
          </button>
        }
      />
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

const DETAIL_RATINGS: { rating: FeedbackRating; labelKey: string }[] = [
  { rating: "useful", labelKey: "chat.feedbackUseful" },
  { rating: "not_useful", labelKey: "chat.feedbackNotUseful" },
  { rating: "factual_error", labelKey: "chat.feedbackFactualError" },
  { rating: "code_error", labelKey: "chat.feedbackCodeError" },
  { rating: "missing_sources", labelKey: "chat.feedbackMissingSources" },
  { rating: "off_topic", labelKey: "chat.feedbackOffTopic" },
  { rating: "incorrect", labelKey: "chat.feedbackIncorrect" },
  { rating: "incomplete", labelKey: "chat.feedbackIncomplete" },
  { rating: "outdated", labelKey: "chat.feedbackOutdated" },
];

export function MessageActions({
  className,
  content,
  userRequest,
  messageId,
  conversationId,
  canEdit,
  canRegenerate,
  regenerateLabel,
  isPending,
  onEdit,
  onRegenerate,
  onStop,
}: {
  className?: string;
  content: string;
  userRequest?: string;
  messageId?: string;
  conversationId?: string;
  canEdit?: boolean;
  canRegenerate?: boolean;
  regenerateLabel?: string;
  isPending?: boolean;
  onEdit?: () => void;
  onRegenerate?: () => void;
  onStop?: () => void;
}) {
  const t = useT();
  const [copied, setCopied] = React.useState(false);
  const [panelOpen, setPanelOpen] = React.useState(false);
  const [note, setNote] = React.useState("");
  const [sent, setSent] = React.useState<string | null>(null);
  const [sending, setSending] = React.useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }

  async function sendRating(rating: FeedbackRating) {
    if (!userRequest || sending || sent) return;
    setSending(true);
    try {
      await submitAnswerFeedback({
        rating,
        user_request: userRequest,
        nexa_response: content,
        note: note.trim() || undefined,
        conversation_id: conversationId,
        message_id: messageId,
      });
      setSent(rating);
      setPanelOpen(false);
    } catch {
      /* feedback optional — do not break chat */
    } finally {
      setSending(false);
    }
  }

  if (isPending) {
    return (
      <div className={cn("flex items-center gap-0.5", className)}>
        <ActionButton label={t("chat.stopGenerating")} onClick={() => onStop?.()}>
          <Square className="size-3.5" aria-hidden="true" />
        </ActionButton>
      </div>
    );
  }

  const showFeedback = Boolean(userRequest && content);

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex items-center gap-0.5">
        <ActionButton label={copied ? t("chat.copied") : t("chat.copy")} onClick={handleCopy}>
          {copied ? (
            <Check className="size-3.5" aria-hidden="true" />
          ) : (
            <Copy className="size-3.5" aria-hidden="true" />
          )}
        </ActionButton>
        {canEdit && (
          <ActionButton label={t("chat.edit")} onClick={() => onEdit?.()}>
            <Pencil className="size-3.5" aria-hidden="true" />
          </ActionButton>
        )}
        {canRegenerate && (
          <ActionButton
            label={regenerateLabel ?? t("chat.regenerate")}
            onClick={() => onRegenerate?.()}
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
          </ActionButton>
        )}
        {showFeedback && (
          <>
            <ActionButton
              label={t("chat.feedbackUseful")}
              active={sent === "useful" || sent === "up"}
              onClick={() => void sendRating("useful")}
            >
              <ThumbsUp className="size-3.5" aria-hidden="true" />
            </ActionButton>
            <ActionButton
              label={t("chat.feedbackTitle")}
              active={panelOpen || (sent != null && sent !== "useful" && sent !== "up")}
              onClick={() => setPanelOpen((v) => !v)}
            >
              <ThumbsDown className="size-3.5" aria-hidden="true" />
            </ActionButton>
          </>
        )}
      </div>
      {sent && (
        <p className="text-[11px] text-muted-foreground">{t("chat.feedbackSent")}</p>
      )}
      {panelOpen && !sent && (
        <div className="rounded-md border border-border/60 bg-background p-2 text-xs shadow-sm">
          <p className="mb-1.5 font-medium">{t("chat.feedbackTitle")}</p>
          <div className="mb-2 flex flex-wrap gap-1">
            {DETAIL_RATINGS.map(({ rating, labelKey }) => (
              <button
                key={rating}
                type="button"
                disabled={sending}
                onClick={() => void sendRating(rating)}
                className="rounded border border-border/60 px-2 py-1 hover:bg-muted"
              >
                {t(labelKey)}
              </button>
            ))}
          </div>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t("chat.feedbackNote")}
            className="w-full rounded border border-border/60 bg-transparent px-2 py-1 text-xs outline-none focus-visible:ring-1 focus-visible:ring-ring"
            aria-label={t("chat.feedbackNote")}
          />
        </div>
      )}
    </div>
  );
}

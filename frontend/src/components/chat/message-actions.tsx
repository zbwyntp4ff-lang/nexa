"use client";
import * as React from "react";
import { Check, Copy, Pencil, RefreshCw, Square } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
function ActionButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <button type="button" onClick={onClick} aria-label={label} className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            {children}
          </button>
        }
      />
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
export function MessageActions({
  className, content, canEdit, canRegenerate, regenerateLabel, isPending, onEdit, onRegenerate, onStop,
}: {
  className?: string; content: string; canEdit?: boolean; canRegenerate?: boolean;
  regenerateLabel?: string; isPending?: boolean;
  onEdit?: () => void; onRegenerate?: () => void; onStop?: () => void;
}) {
  const t = useT();
  const [copied, setCopied] = React.useState(false);
  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard unavailable */ }
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
  return (
    <div className={cn("flex items-center gap-0.5", className)}>
      <ActionButton label={copied ? t("chat.copied") : t("chat.copy")} onClick={handleCopy}>
        {copied ? <Check className="size-3.5" aria-hidden="true" /> : <Copy className="size-3.5" aria-hidden="true" />}
      </ActionButton>
      {canEdit && (
        <ActionButton label={t("chat.edit")} onClick={() => onEdit?.()}>
          <Pencil className="size-3.5" aria-hidden="true" />
        </ActionButton>
      )}
      {canRegenerate && (
        <ActionButton label={regenerateLabel ?? t("chat.regenerate")} onClick={() => onRegenerate?.()}>
          <RefreshCw className="size-3.5" aria-hidden="true" />
        </ActionButton>
      )}
    </div>
  );
}

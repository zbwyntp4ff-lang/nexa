"use client";
import * as React from "react";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { useHexaStore, type HexaTurn } from "@/store/hexa-store";

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function TurnBubble({ turn }: { turn: HexaTurn }) {
  const t = useT();
  const isUser = turn.role === "user";
  return (
    <div className={cn("flex flex-col gap-0.5", isUser ? "items-end" : "items-start")}>
      <div className="flex items-center gap-1.5 text-[9px] tracking-wide text-white/40 uppercase">
        <span>{isUser ? t("hexa.you") : t("hexa.assistant")}</span>
        <span className="normal-case tracking-normal">{formatTime(turn.at)}</span>
      </div>
      <div
        className={cn(
          "max-w-[95%] rounded-xl px-2.5 py-1.5 text-[12px] leading-snug",
          isUser
            ? "rounded-br-md bg-white/12 text-white"
            : "rounded-bl-md border border-white/10 bg-white/[0.06] text-white/85"
        )}
      >
        {turn.content}
      </div>
    </div>
  );
}

export function HexaHistory() {
  const t = useT();
  const history = useHexaStore((s) => s.history);
  const clearHistory = useHexaStore((s) => s.clearHistory);
  const listRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [history.length]);

  return (
    <aside className="hexa-history flex h-full max-h-full min-h-0 w-full flex-col rounded-xl border border-white/10 bg-white/[0.04] backdrop-blur-md">
      <div className="flex items-center justify-between gap-2 border-b border-white/10 px-2.5 py-1.5">
        <p className="text-[10px] font-semibold tracking-[0.18em] text-white/55 uppercase">
          {t("hexa.history")}
        </p>
        {history.length > 0 && (
          <button
            type="button"
            onClick={clearHistory}
            className="text-[10px] text-white/45 transition-colors hover:text-white/80"
          >
            {t("hexa.historyClear")}
          </button>
        )}
      </div>
      <div ref={listRef} className="nexa-scrollbar min-h-0 flex-1 space-y-2 overflow-y-auto px-2 py-2">
        {history.length === 0 ? (
          <p className="px-1 py-4 text-center text-[11px] leading-relaxed text-white/35">
            {t("hexa.historyEmpty")}
          </p>
        ) : (
          history.map((turn) => <TurnBubble key={turn.id} turn={turn} />)
        )}
      </div>
    </aside>
  );
}

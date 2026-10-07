"use client";
import * as React from "react";
import { Message } from "./message";
import type { ChatMessageView } from "@/lib/types";
export function Conversation({
  messages,
  onRetry,
  onEdit,
  onStop,
}: {
  messages: ChatMessageView[];
  onRetry: (assistantMessageId: string) => void;
  onEdit: (userMessageId: string, newContent: string) => void;
  onStop: () => void;
}) {
  const bottomRef = React.useRef<HTMLDivElement | null>(null);
  const lastMessage = messages[messages.length - 1];
  const lastMessageContent = lastMessage?.content;
  const lastMessagePending = lastMessage?.pending;
  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, lastMessageContent, lastMessagePending]);
  return (
    <div
      className="mx-auto w-full max-w-3xl pb-4"
      role="log"
      aria-live="polite"
      aria-label="Conversation"
    >
      {messages.map((message) => (
        <Message
          key={message.id}
          message={message}
          onRetry={() => onRetry(message.id)}
          onEdit={(newContent) => onEdit(message.id, newContent)}
          onStop={onStop}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

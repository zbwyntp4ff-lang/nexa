"use client";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ComingSoonBanner } from "./coming-soon-banner";
import { Composer } from "./composer";
import { Conversation } from "./conversation";
import { EmptyState } from "./empty-state";
import { cn } from "@/lib/utils";
import { AVAILABLE_MODES } from "@/lib/types";
import { MODE_GRADIENT } from "@/lib/mode-theme";
import { pluginGatingMode } from "@/lib/plugins";
import { useChatStore } from "@/store/chat-store";
import { usePluginsStore } from "@/store/plugins-store";
import { useUiStore } from "@/store/ui-store";
import { useConversationController } from "@/hooks/use-conversation-controller";
export function ChatPanel() {
  const conversations = useChatStore((s) => s.conversations);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const createConversation = useChatStore((s) => s.createConversation);
  const pendingMode = useUiStore((s) => s.pendingMode);
  const activeConversation = conversations.find((c) => c.id === activeConversationId);
  const mode = activeConversation?.mode ?? pendingMode;
  const enabledPlugins = usePluginsStore((s) => s.enabled);
  const gatingPlugin = pluginGatingMode(mode);
  const pluginOff = gatingPlugin ? !enabledPlugins[gatingPlugin] : false;
  const isAvailable = AVAILABLE_MODES.has(mode) && !pluginOff;
  const { send, retry, edit, stop, isSending, sendingConversationId } = useConversationController();
  function ensureConversationId(): string {
    if (activeConversation) return activeConversation.id;
    return createConversation(mode);
  }
  function handleSend(text: string, attachments?: Parameters<typeof send>[2]) {
    const id = ensureConversationId();
    void send(id, text, attachments);
  }
  const isSendingHere = isSending && sendingConversationId === (activeConversation?.id ?? sendingConversationId);
  if (!isAvailable) {
    return <ComingSoonBanner mode={mode} reason={pluginOff ? "plugin" : "soon"} />;
  }
  return (
    <div className="flex h-full min-h-0 flex-col bg-transparent">
      <div
        key={`bar-${mode}`}
        className={cn("nexa-fade-in h-0.5 w-full shrink-0 opacity-80", MODE_GRADIENT[mode])}
        aria-hidden="true"
      />
      <ScrollArea key={`panel-${mode}`} className="min-h-0 flex-1 nexa-scrollbar nexa-fade-in">
        {activeConversation && activeConversation.messages.length > 0 ? (
          <Conversation
            messages={activeConversation.messages}
            onRetry={(messageId) => retry(activeConversation.id, messageId)}
            onEdit={(messageId, newContent) => edit(activeConversation.id, messageId, newContent)}
            onStop={stop}
          />
        ) : (
          <EmptyState mode={mode} onSuggestionClick={(text) => handleSend(text)} />
        )}
      </ScrollArea>
      <Composer mode={mode} onSend={handleSend} onStop={stop} isSending={isSendingHere} />
    </div>
  );
}

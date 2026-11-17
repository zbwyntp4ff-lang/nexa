"use client";
import * as React from "react";
import { Trash2, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useChatStore } from "@/store/chat-store";
import { useUiStore } from "@/store/ui-store";
import { useI18nStore, type Language } from "@/lib/i18n-store";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const LANGUAGES: { value: Language; label: string; flag: string }[] = [
  { value: "en", label: "English", flag: "EN" },
  { value: "ru", label: "Русский", flag: "RU" },
];

export function GeneralSection() {
  const t = useT();
  const conversations = useChatStore((s) => s.conversations);
  const clearAllChats = useChatStore((s) => s.clearAllChats);
  const language = useI18nStore((s) => s.language);
  const setLanguage = useI18nStore((s) => s.setLanguage);
  const enterToSend = useUiStore((s) => s.enterToSend);
  const setEnterToSend = useUiStore((s) => s.setEnterToSend);
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium">{t("general.application")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("general.appDesc")}</p>
      </div>
      <div className="space-y-2">
        <h3 className="flex items-center gap-1.5 text-sm font-medium">
          <Globe className="size-4" aria-hidden="true" />
          {t("general.language")}
        </h3>
        <p className="text-sm text-muted-foreground">{t("general.languageDesc")}</p>
        <div
          role="radiogroup"
          aria-label={t("general.language")}
          className="flex items-center gap-1 rounded-lg border border-border bg-muted/50 p-1"
        >
          {LANGUAGES.map(({ value, label, flag }) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={language === value}
              onClick={() => setLanguage(value)}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                language === value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <span className="text-[10px] font-bold tracking-wide opacity-60">{flag}</span>
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-center justify-between gap-4 rounded-lg border border-border p-3">
        <div>
          <p className="text-sm font-medium">{t("general.enterToSend")}</p>
          <p className="mt-1 text-xs text-muted-foreground">{t("general.enterToSendDesc")}</p>
        </div>
        <Switch checked={enterToSend} onCheckedChange={setEnterToSend} aria-label={t("general.enterToSend")} />
      </div>
      <div className="space-y-2">
        <h3 className="text-sm font-medium">{t("general.data")}</h3>
        <p className="text-sm text-muted-foreground">
          {t("general.appDesc").split(".")[0]}. {conversations.length} saved{" "}
          {conversations.length === 1 ? "chat" : "chats"}.
        </p>
        <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <AlertDialogTrigger
            render={
              <Button variant="outline" className="text-destructive hover:text-destructive">
                <Trash2 className="size-4" aria-hidden="true" />
                {t("general.clearAllChats")}
              </Button>
            }
          />
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t("general.clearAllChatsConfirm")}</AlertDialogTitle>
              <AlertDialogDescription>{t("general.clearAllChatsDesc")}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t("chat.cancel")}</AlertDialogCancel>
              <AlertDialogAction onClick={() => clearAllChats()}>{t("general.clearAll")}</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
}

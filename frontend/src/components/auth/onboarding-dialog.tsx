"use client";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n";
import type { ResponseStyle } from "@/lib/profile-api";
import { useProfileStore } from "@/store/profile-store";

const STYLES: ResponseStyle[] = ["concise", "balanced", "detailed", "technical"];

export function OnboardingDialog({ onDone }: { onDone: () => void }) {
  const t = useT();
  const profile = useProfileStore((s) => s.profile);
  const load = useProfileStore((s) => s.load);
  const save = useProfileStore((s) => s.save);
  const [step, setStep] = React.useState(0);
  const [displayName, setDisplayName] = React.useState("");
  const [uiLanguage, setUiLanguage] = React.useState("");
  const [style, setStyle] = React.useState<ResponseStyle>("balanced");
  const [model, setModel] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    void load().then(() => {
      /* profile hydrated below */
    });
  }, [load]);

  React.useEffect(() => {
    if (!profile) return;
    setDisplayName(profile.display_name);
    setUiLanguage(profile.ui_language);
    setStyle(profile.ai.response_style);
    setModel(profile.ai.default_model ?? "");
  }, [profile]);

  async function finish(skip: boolean) {
    setBusy(true);
    try {
      if (!skip) {
        await save({
          display_name: displayName,
          ui_language: uiLanguage,
          ai: {
            ...(profile?.ai ?? {
              personalization_enabled: true,
              response_style: "balanced",
              personality: "friendly",
              brevity: "medium",
              detail_level: "medium",
              answer_format: "auto",
              ai_language: "",
              default_model: null,
              preferred_name: "",
              custom_instructions: "",
              about_user: "",
              occupation: "",
              interests: [],
              avoid_topics: "",
              expertise_level: "intermediate",
              proactive_suggestions: true,
            }),
            response_style: style,
            default_model: model.trim() || null,
          },
          onboarding_completed: true,
        });
      } else {
        await save({ onboarding_completed: true });
      }
      onDone();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-border bg-background p-6 shadow-xl">
        <h1 className="text-xl font-semibold">{t("onboarding.welcome")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("onboarding.subtitle")}</p>

        {step === 0 && (
          <label className="mt-5 flex flex-col gap-1.5 text-sm">
            <span className="font-medium">{t("personalization.displayName")}</span>
            <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="h-10" />
          </label>
        )}
        {step === 1 && (
          <label className="mt-5 flex flex-col gap-1.5 text-sm">
            <span className="font-medium">{t("onboarding.language")}</span>
            <Input
              value={uiLanguage}
              onChange={(e) => setUiLanguage(e.target.value)}
              placeholder="en / ru"
              className="h-10"
            />
          </label>
        )}
        {step === 2 && (
          <label className="mt-5 flex flex-col gap-1.5 text-sm">
            <span className="font-medium">{t("personalization.responseStyle")}</span>
            <select
              className="h-10 rounded-lg border border-input bg-transparent px-2.5"
              value={style}
              onChange={(e) => setStyle(e.target.value as ResponseStyle)}
            >
              {STYLES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        )}
        {step === 3 && (
          <label className="mt-5 flex flex-col gap-1.5 text-sm">
            <span className="font-medium">{t("personalization.defaultModel")}</span>
            <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="auto" className="h-10" />
          </label>
        )}

        <div className="mt-6 flex flex-wrap gap-2">
          {step < 3 ? (
            <Button type="button" onClick={() => setStep((s) => s + 1)}>
              {t("onboarding.next")}
            </Button>
          ) : (
            <Button type="button" disabled={busy} onClick={() => void finish(false)}>
              {t("onboarding.start")}
            </Button>
          )}
          <Button type="button" variant="ghost" disabled={busy} onClick={() => void finish(true)}>
            {t("onboarding.skip")}
          </Button>
        </div>
      </div>
    </div>
  );
}

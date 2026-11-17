"use client";
import * as React from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n";
import type { AnswerFormat, DetailLevel, Personality, ResponseStyle } from "@/lib/profile-api";
import { fetchContextPreview } from "@/lib/profile-api";
import { useProfileStore } from "@/store/profile-store";

const STYLES: ResponseStyle[] = ["concise", "balanced", "detailed", "technical"];
const PERSONALITIES: Personality[] = ["professional", "friendly", "direct", "technical"];
const LEVELS: DetailLevel[] = ["low", "medium", "high"];
const FORMATS: AnswerFormat[] = ["auto", "prose", "bullets", "structured"];

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <select
        className="h-10 rounded-lg border border-input bg-transparent px-2.5 text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}

export function PersonalizationSection() {
  const t = useT();
  const profile = useProfileStore((s) => s.profile);
  const loading = useProfileStore((s) => s.loading);
  const load = useProfileStore((s) => s.load);
  const save = useProfileStore((s) => s.save);
  const patchAi = useProfileStore((s) => s.patchAi);
  const [displayName, setDisplayName] = React.useState("");
  const [preferredName, setPreferredName] = React.useState("");
  const [aiLanguage, setAiLanguage] = React.useState("");
  const [defaultModel, setDefaultModel] = React.useState("");
  const [aboutUser, setAboutUser] = React.useState("");
  const [occupation, setOccupation] = React.useState("");
  const [interests, setInterests] = React.useState("");
  const [customInstructions, setCustomInstructions] = React.useState("");
  const [avoidTopics, setAvoidTopics] = React.useState("");
  const [expertiseLevel, setExpertiseLevel] = React.useState<"beginner" | "intermediate" | "advanced" | "expert">("intermediate");
  const [proactiveSuggestions, setProactiveSuggestions] = React.useState(true);
  const [hint, setHint] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    void load();
  }, [load]);

  React.useEffect(() => {
    if (!profile) return;
    setDisplayName(profile.display_name);
    setPreferredName(profile.ai.preferred_name);
    setAiLanguage(profile.ai.ai_language);
    setDefaultModel(profile.ai.default_model ?? "");
    setAboutUser(profile.ai.about_user ?? "");
    setOccupation(profile.ai.occupation ?? "");
    setInterests((profile.ai.interests ?? []).join(", "));
    setCustomInstructions(profile.ai.custom_instructions ?? "");
    setAvoidTopics(profile.ai.avoid_topics ?? "");
    setExpertiseLevel(profile.ai.expertise_level ?? "intermediate");
    setProactiveSuggestions(profile.ai.proactive_suggestions ?? true);
  }, [profile]);

  async function persistProfile() {
    setBusy(true);
    try {
      await save({
        display_name: displayName,
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
          preferred_name: preferredName,
          ai_language: aiLanguage,
          default_model: defaultModel.trim() || null,
          about_user: aboutUser,
          occupation,
          interests: interests.split(",").map((item) => item.trim()).filter(Boolean).slice(0, 12),
          custom_instructions: customInstructions,
          avoid_topics: avoidTopics,
          expertise_level: expertiseLevel,
          proactive_suggestions: proactiveSuggestions,
        },
      });
      const preview = await fetchContextPreview();
      setHint(preview.hint);
    } finally {
      setBusy(false);
    }
  }

  async function onAvatar(file: File | null) {
    if (!file || !file.type.startsWith("image/")) return;
    if (file.size > 80_000) return;
    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = String(reader.result || "");
      if (!dataUrl.startsWith("data:image/")) return;
      await save({ avatar_data_url: dataUrl });
    };
    reader.readAsDataURL(file);
  }

  if (loading && !profile) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> {t("personalization.loading")}
      </div>
    );
  }

  const ai = profile?.ai;

  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-base font-semibold">{t("personalization.title")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("personalization.desc")}</p>
      </div>

      <section className="space-y-3">
        <h4 className="text-sm font-medium">{t("personalization.profile")}</h4>
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium">{t("personalization.displayName")}</span>
          <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="h-10" />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium">{t("personalization.avatar")}</span>
          <div className="flex items-center gap-3">
            {profile?.avatar_data_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={profile.avatar_data_url} alt="" className="size-12 rounded-full object-cover" />
            ) : (
              <div className="size-12 rounded-full bg-muted" />
            )}
            <Input
              type="file"
              accept="image/*"
              className="h-10"
              onChange={(e) => void onAvatar(e.target.files?.[0] ?? null)}
            />
          </div>
          <span className="text-xs text-muted-foreground">{t("personalization.avatarHint")}</span>
        </label>
      </section>

      <section className="space-y-3">
        <h4 className="text-sm font-medium">{t("personalization.aiPrefs")}</h4>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={ai?.personalization_enabled ?? true}
            onChange={(e) => void patchAi({ personalization_enabled: e.target.checked })}
          />
          {t("personalization.enabled")}
        </label>
        <SelectField
          label={t("personalization.responseStyle")}
          value={ai?.response_style ?? "balanced"}
          options={STYLES}
          onChange={(v) => void patchAi({ response_style: v as ResponseStyle })}
        />
        <SelectField
          label={t("personalization.personality")}
          value={ai?.personality ?? "friendly"}
          options={PERSONALITIES}
          onChange={(v) => void patchAi({ personality: v as Personality })}
        />
        <SelectField
          label={t("personalization.brevity")}
          value={ai?.brevity ?? "medium"}
          options={LEVELS}
          onChange={(v) => void patchAi({ brevity: v as DetailLevel })}
        />
        <SelectField
          label={t("personalization.detail")}
          value={ai?.detail_level ?? "medium"}
          options={LEVELS}
          onChange={(v) => void patchAi({ detail_level: v as DetailLevel })}
        />
        <SelectField
          label={t("personalization.format")}
          value={ai?.answer_format ?? "auto"}
          options={FORMATS}
          onChange={(v) => void patchAi({ answer_format: v as AnswerFormat })}
        />
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium">{t("personalization.aiLanguage")}</span>
          <Input
            value={aiLanguage}
            onChange={(e) => setAiLanguage(e.target.value)}
            placeholder={t("personalization.aiLanguageHint")}
            className="h-10"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium">{t("personalization.preferredName")}</span>
          <Input value={preferredName} onChange={(e) => setPreferredName(e.target.value)} className="h-10" />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium">{t("personalization.defaultModel")}</span>
          <Input
            value={defaultModel}
            onChange={(e) => setDefaultModel(e.target.value)}
            placeholder="auto"
            className="h-10"
          />
        </label>
      </section>

      <section className="space-y-2">
        <h4 className="text-sm font-medium">{t("personalization.memory")}</h4>
        <p className="text-sm text-muted-foreground">{t("personalization.memoryDesc")}</p>
        {hint && (
          <pre className="overflow-x-auto rounded-lg border border-border bg-muted/30 p-3 text-xs whitespace-pre-wrap">
            {hint}
          </pre>
        )}
      </section>

      <Button type="button" disabled={busy} onClick={() => void persistProfile()}>
        {busy ? t("personalization.saving") : t("personalization.save")}
      </Button>
    </div>
  );
}

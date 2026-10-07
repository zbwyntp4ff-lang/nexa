"use client";
import * as React from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ApiError, checkModel, getGatewayModels, updateModelSelection } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { GatewayModelCard, GatewayModelsResponse } from "@/lib/types";
const PROVIDERS = ["auto", "openai", "anthropic", "ollama"] as const;
function providerLabel(provider: string): string {
  if (provider === "openai") return "OpenAI";
  if (provider === "anthropic") return "Anthropic";
  if (provider === "ollama") return "Ollama";
  return provider;
}
export function ModelsSection() {
  const t = useT();
  const [state, setState] = React.useState<"loading" | "ready" | "error">("loading");
  const [data, setData] = React.useState<GatewayModelsResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [provider, setProvider] = React.useState("auto");
  const [model, setModel] = React.useState("auto");
  const [fallback, setFallback] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [checking, setChecking] = React.useState(false);
  const [checkResult, setCheckResult] = React.useState<GatewayModelCard | null>(null);
  const apply = React.useCallback((payload: GatewayModelsResponse) => {
    const nextProvider = payload.selection_mode === "auto" ? "auto" : (payload.provider ?? "auto");
    let nextModel = payload.selection_mode === "auto" ? "auto" : (payload.model ?? "auto");
    if (nextModel !== "auto" && !payload.models.some((item) => item.model_id === nextModel)) {
      const match = payload.models.find(
        (item) => item.provider === nextProvider && item.model_id.split(":")[0] === nextModel,
      );
      if (match) nextModel = match.model_id;
    }
    setData(payload);
    setProvider(nextProvider);
    setModel(nextModel);
    setFallback(payload.allow_fallback);
    setState("ready");
  }, []);
  React.useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setState("loading");
      try {
        apply(await getGatewayModels(controller.signal));
      } catch (err) {
        if ((err as Error)?.name === "AbortError") return;
        setError(err instanceof ApiError ? err.message : "Could not reach the NEXA backend.");
        setState("error");
      }
    }
    void load();
    return () => controller.abort();
  }, [apply]);
  const models = data?.models ?? [];
  const visible = provider === "auto" ? models : models.filter((item) => item.provider === provider);
  async function save(next: { provider: string; model: string; allow_fallback: boolean }) {
    setSaving(true);
    setError(null);
    try {
      apply(await updateModelSelection(next));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update the model selection.");
    } finally {
      setSaving(false);
    }
  }
  function reasonText(reason: string | null | undefined): string | null {
    if (reason === "missing_api_key") return t("models.missingKey");
    if (reason === "not_installed") return t("models.notInstalled");
    if (reason === "provider_unavailable") return t("models.providerDown");
    return null;
  }
  const activeReason = reasonText(checkResult?.availability_reason ?? data?.availability_reason);
  const activeAvailable = (checkResult?.availability ?? data?.availability) === "available";
  const activeCard = data
    ? models.find((item) => item.provider === data.active_provider && item.model_id === data.active_model)
    : undefined;
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium">{t("models.activeModel")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("models.modelDesc")}</p>
      </div>
      {state === "loading" && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" /> {t("models.checking")}
        </p>
      )}
      {state === "error" && (
        <p className="flex items-center gap-2 text-sm text-destructive">
          <XCircle className="size-4" aria-hidden="true" /> {error}
        </p>
      )}
      {state === "ready" && data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="nexa-provider">{t("models.provider")}</Label>
              <Select
                value={provider}
                onValueChange={(value) => {
                  if (!value) return;
                  const nextModel = value === "auto"
                    ? "auto"
                    : (models.find((item) => item.provider === value)?.model_id ?? "auto");
                  setProvider(value);
                  setModel(nextModel);
                  void save({ provider: value, model: nextModel, allow_fallback: fallback });
                }}
              >
                <SelectTrigger id="nexa-provider" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PROVIDERS.map((item) => (
                    <SelectItem key={item} value={item}>
                      {item === "auto" ? t("models.auto") : providerLabel(item)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="nexa-model">{t("models.model")}</Label>
              <Select
                value={model}
                onValueChange={(value) => {
                  if (!value) return;
                  setModel(value);
                  const nextProvider = value === "auto" ? "auto" : provider === "auto" ? (models.find((item) => item.model_id === value)?.provider ?? "auto") : provider;
                  setProvider(nextProvider);
                  void save({ provider: nextProvider, model: value, allow_fallback: fallback });
                }}
              >
                <SelectTrigger id="nexa-model" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">{t("models.auto")}</SelectItem>
                  {visible.map((item) => (
                    <SelectItem key={`${item.provider}:${item.model_id}`} value={item.model_id}>
                      {item.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex items-start justify-between gap-3 rounded-lg border border-border p-3">
            <div>
              <p className="text-sm font-medium">{t("models.fallback")}</p>
              <p className="mt-1 text-xs text-muted-foreground">{t("models.fallbackDesc")}</p>
            </div>
            <Switch
              checked={fallback}
              onCheckedChange={(checked) => {
                setFallback(checked);
                void save({ provider, model, allow_fallback: checked });
              }}
              aria-label={t("models.fallback")}
            />
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-border p-3 text-sm">
            <dt className="text-muted-foreground">{t("models.current")}</dt>
            <dd className="font-medium">{providerLabel(data.active_provider)} · {data.active_display_name ?? data.active_model}</dd>
            <dt className="text-muted-foreground">{t("models.availability")}</dt>
            <dd className="flex items-center gap-1.5 font-medium">
              {activeAvailable ? (
                <><CheckCircle2 className="size-3.5 text-success" aria-hidden="true" /> {t("models.available")}</>
              ) : (
                <><XCircle className="size-3.5 text-destructive" aria-hidden="true" /> {t("models.unavailable")}</>
              )}
            </dd>
            {data.last_model && (
              <>
                <dt className="text-muted-foreground">{t("models.lastAnswer")}</dt>
                <dd className="font-medium">{providerLabel(data.last_provider ?? "")} · {data.last_display_name ?? data.last_model}</dd>
              </>
            )}
            {activeCard && (
              <>
                <dt className="text-muted-foreground">{t("models.visionSupport")}</dt>
                <dd className="font-medium">{activeCard.supports_vision ? t("models.yes") : t("models.no")}</dd>
              </>
            )}
          </dl>
          {activeReason && (
            <p className="flex items-start gap-2 text-sm text-destructive">
              <XCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" /> {activeReason}
            </p>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={checking || saving || model === "auto"}
              onClick={() => {
                setChecking(true);
                setError(null);
                void checkModel(model, true)
                  .then((card) => setCheckResult(card))
                  .catch((err) => setError(err instanceof ApiError ? err.message : "Check failed."))
                  .finally(() => setChecking(false));
              }}
            >
              {checking ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : t("models.check")}
            </Button>
            <p className="text-xs text-muted-foreground">{t("models.keysStay")}</p>
          </div>
        </>
      )}
    </div>
  );
}

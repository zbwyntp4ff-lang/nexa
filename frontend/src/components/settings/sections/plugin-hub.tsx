"use client";
import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  connectHubPlugin,
  diagnoseHubPlugin,
  disconnectHubPlugin,
  getHubPlugin,
  invokeHubPlugin,
  listHubPlugins,
  patchHubPluginPermissions,
  type PluginCardApi,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const CATEGORIES = ["", "editor", "git", "browser", "3d", "game"] as const;

function statusLabel(t: (k: string) => string, status: string) {
  return t(`pluginHub.status.${status}`) !== `pluginHub.status.${status}`
    ? t(`pluginHub.status.${status}`)
    : status;
}

export function PluginHub() {
  const t = useT();
  const [query, setQuery] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [items, setItems] = React.useState<PluginCardApi[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [detail, setDetail] = React.useState<PluginCardApi | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [token, setToken] = React.useState("");
  const [permissions, setPermissions] = React.useState<string[]>([]);
  const [diag, setDiag] = React.useState<string>("");

  const loadList = React.useCallback(async () => {
    setError(null);
    try {
      const res = await listHubPlugins(query, category);
      setItems(res.plugins);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("pluginHub.loadError"));
    }
  }, [query, category, t]);

  React.useEffect(() => {
    void loadList();
  }, [loadList]);

  React.useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const card = await getHubPlugin(selectedId);
        if (cancelled) return;
        setDetail(card);
        setPermissions(card.granted_permissions.length ? card.granted_permissions : card.required_permissions);
        setToken("");
        setDiag("");
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : t("pluginHub.loadError"));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId, t]);

  async function refreshSelected() {
    if (!selectedId) return;
    const card = await getHubPlugin(selectedId);
    setDetail(card);
    setPermissions(card.granted_permissions.length ? card.granted_permissions : card.required_permissions);
    await loadList();
  }

  async function onConnect() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const body: { permissions: string[]; token?: string } = { permissions };
      if (token.trim()) body.token = token.trim();
      const card = await connectHubPlugin(selectedId, body);
      setDetail(card);
      setToken("");
      if (!card.enabled) {
        setError(card.last_error || t("pluginHub.connectFailed"));
      }
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("pluginHub.connectFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function onDisconnect() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      setDetail(await disconnectHubPlugin(selectedId));
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("pluginHub.disconnectFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function onDiagnose() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await diagnoseHubPlugin(selectedId);
      setDiag(JSON.stringify(res.probe, null, 2));
      await refreshSelected();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("pluginHub.diagnoseFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function onSavePermissions() {
    if (!selectedId || !detail?.enabled) return;
    setBusy(true);
    setError(null);
    try {
      setDetail(await patchHubPluginPermissions(selectedId, permissions));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("pluginHub.permFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function onSafeAction(action: string) {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await invokeHubPlugin(selectedId, { action, params: {}, confirm: false });
      setDiag(JSON.stringify(res.result, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("pluginHub.invokeFailed"));
    } finally {
      setBusy(false);
    }
  }

  const allPerms = detail
    ? Array.from(new Set([...detail.required_permissions, ...detail.optional_permissions]))
    : [];
  const safeAction = detail?.actions.find((a) => !a.dangerous);

  return (
    <div className="space-y-4 border-t border-border pt-6">
      <div>
        <h3 className="text-sm font-medium">{t("pluginHub.title")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("pluginHub.desc")}</p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("pluginHub.search")}
          aria-label={t("pluginHub.search")}
        />
        <select
          className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          aria-label={t("pluginHub.category")}
        >
          {CATEGORIES.map((c) => (
            <option key={c || "all"} value={c}>
              {c ? t(`pluginHub.cat.${c}`) : t("pluginHub.cat.all")}
            </option>
          ))}
        </select>
      </div>
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <ul className="space-y-2">
        {items.map((plugin) => (
          <li key={plugin.id}>
            <button
              type="button"
              onClick={() => setSelectedId(plugin.id)}
              className={cn(
                "flex w-full items-start justify-between gap-3 rounded-lg border p-3 text-left",
                selectedId === plugin.id ? "border-ring bg-muted/40" : "border-border",
              )}
            >
              <div>
                <p className="text-sm font-medium">{plugin.name}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{plugin.description}</p>
              </div>
              <Badge variant={plugin.enabled ? "default" : "secondary"}>
                {statusLabel(t, plugin.status)}
              </Badge>
            </button>
          </li>
        ))}
      </ul>
      {detail ? (
        <div className="space-y-3 rounded-lg border border-border p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">
              {detail.name}{" "}
              <span className="font-normal text-muted-foreground">v{detail.version}</span>
            </h4>
            <Badge variant={detail.enabled ? "default" : "outline"}>{statusLabel(t, detail.status)}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">{detail.description}</p>
          <p className="text-xs text-muted-foreground">
            {t("pluginHub.category")}: {t(`pluginHub.cat.${detail.category}`)} · {detail.integration_type}
          </p>
          <div>
            <p className="text-xs font-medium">{t("pluginHub.dependencies")}</p>
            <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
              {detail.dependencies.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          </div>
          <p className="text-xs text-muted-foreground">{detail.install_hint}</p>
          {detail.last_error ? (
            <p className="text-sm text-destructive" role="alert">
              {detail.last_error}
            </p>
          ) : null}
          <fieldset className="space-y-1">
            <legend className="text-xs font-medium">{t("pluginHub.permissions")}</legend>
            {allPerms.map((perm) => (
              <label key={perm} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={permissions.includes(perm)}
                  onChange={(e) =>
                    setPermissions((prev) =>
                      e.target.checked ? [...prev, perm] : prev.filter((p) => p !== perm),
                    )
                  }
                />
                {perm}
                {detail.required_permissions.includes(perm) ? (
                  <span className="text-xs text-muted-foreground">{t("pluginHub.required")}</span>
                ) : null}
              </label>
            ))}
          </fieldset>
          {detail.id === "github" && !detail.enabled ? (
            <Input
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder={t("pluginHub.githubToken")}
              aria-label={t("pluginHub.githubToken")}
            />
          ) : null}
          {detail.has_token ? <p className="text-xs text-muted-foreground">{t("pluginHub.tokenStored")}</p> : null}
          <div className="flex flex-wrap gap-2">
            {detail.enabled ? (
              <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void onDisconnect()}>
                {t("pluginHub.disconnect")}
              </Button>
            ) : (
              <Button type="button" size="sm" disabled={busy} onClick={() => void onConnect()}>
                {t("pluginHub.connect")}
              </Button>
            )}
            <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void onDiagnose()}>
              {t("pluginHub.diagnose")}
            </Button>
            {detail.enabled ? (
              <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void onSavePermissions()}>
                {t("pluginHub.savePerms")}
              </Button>
            ) : null}
            {detail.enabled && safeAction ? (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => void onSafeAction(safeAction.name)}
              >
                {t("pluginHub.runSafe")}: {safeAction.name}
              </Button>
            ) : null}
          </div>
          {diag ? (
            <pre className="max-h-48 overflow-auto rounded-md bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap">
              {diag}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

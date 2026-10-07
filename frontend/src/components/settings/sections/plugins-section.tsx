"use client";
import { Switch } from "@/components/ui/switch";
import { useT } from "@/lib/i18n";
import { PLUGINS } from "@/lib/plugins";
import { usePluginsStore } from "@/store/plugins-store";

export function PluginsSection() {
  const t = useT();
  const enabled = usePluginsStore((s) => s.enabled);
  const setPlugin = usePluginsStore((s) => s.setPlugin);
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium">{t("plugins.title")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("plugins.desc")}</p>
      </div>
      <ul className="space-y-2">
        {PLUGINS.map((plugin) => {
          const Icon = plugin.icon;
          const isOn = enabled[plugin.id];
          return (
            <li
              key={plugin.id}
              className="flex items-start justify-between gap-3 rounded-lg border border-border p-3"
            >
              <div className="flex min-w-0 flex-1 items-start gap-2.5">
                <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-muted">
                  <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
                </div>
                <div>
                  <p className="text-sm font-medium">{t(`plugins.${plugin.id}.name`)}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {t(`plugins.${plugin.id}.desc`)}
                  </p>
                </div>
              </div>
              <Switch
                checked={isOn}
                onCheckedChange={(checked) => setPlugin(plugin.id, checked)}
                aria-label={t(`plugins.${plugin.id}.name`)}
              />
            </li>
          );
        })}
      </ul>
    </div>
  );
}

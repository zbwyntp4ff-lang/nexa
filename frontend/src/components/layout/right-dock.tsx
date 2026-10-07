"use client";
import * as React from "react";
import {
  BookOpen,
  Code2,
  Crown,
  FileUp,
  FolderKanban,
  Globe,
  ListTodo,
  Sparkles,
} from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getGatewayModels } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { PLUGINS, type PluginId } from "@/lib/plugins";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/store/chat-store";
import { usePluginsStore } from "@/store/plugins-store";
import { useUiStore } from "@/store/ui-store";

const DOCK_PLUGIN_IDS: PluginId[] = ["web_search", "calculator", "file_system"];

function Sparkline({ points }: { points: number[] }) {
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const range = Math.max(max - min, 1);
  const d = points
    .map((p, i) => {
      const x = (i / Math.max(points.length - 1, 1)) * 100;
      const y = 28 - ((p - min) / range) * 24;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox="0 0 100 32" className="h-8 w-full" aria-hidden="true">
      <path d={d} fill="none" stroke="url(#nexaSpark)" strokeWidth="2" strokeLinecap="round" />
      <defs>
        <linearGradient id="nexaSpark" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="var(--nexa-violet)" />
          <stop offset="100%" stopColor="var(--nexa-cyan)" />
        </linearGradient>
      </defs>
    </svg>
  );
}

function useSystemStats() {
  const [cpu, setCpu] = React.useState(12);
  const [ramUsed, setRamUsed] = React.useState(38);
  const [ramAvail, setRamAvail] = React.useState(23);
  React.useEffect(() => {
    const tick = () => {
      const mem = (performance as Performance & { memory?: { usedJSHeapSize: number; jsHeapSizeLimit: number } }).memory;
      if (mem?.jsHeapSizeLimit) {
        const usedPct = Math.round((mem.usedJSHeapSize / mem.jsHeapSizeLimit) * 100);
        setRamUsed(Math.min(92, Math.max(8, usedPct)));
        setRamAvail(Math.max(5, 100 - usedPct));
      } else {
        setRamUsed((v) => Math.min(70, Math.max(20, v + (Math.random() * 4 - 2))));
        setRamAvail((v) => Math.min(60, Math.max(10, v + (Math.random() * 3 - 1.5))));
      }
      setCpu((v) => Math.min(55, Math.max(6, v + (Math.random() * 6 - 3))));
    };
    tick();
    const id = window.setInterval(tick, 2200);
    return () => window.clearInterval(id);
  }, []);
  return { cpu, ramUsed, ramAvail };
}

export function RightDock() {
  const t = useT();
  const createConversation = useChatStore((s) => s.createConversation);
  const createProject = useChatStore((s) => s.createProject);
  const openSettings = useUiStore((s) => s.openSettings);
  const openProjects = useUiStore((s) => s.openProjects);
  const enabled = usePluginsStore((s) => s.enabled);
  const setPlugin = usePluginsStore((s) => s.setPlugin);
  const { cpu, ramUsed, ramAvail } = useSystemStats();
  const [modelLabel, setModelLabel] = React.useState("Auto");
  const [spark, setSpark] = React.useState(() => Array.from({ length: 14 }, () => 8 + Math.random() * 16));
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    const controller = new AbortController();
    getGatewayModels(controller.signal)
      .then((data) => {
        if (data.selection_mode === "auto") setModelLabel("Auto");
        else setModelLabel(data.model || data.provider || "Auto");
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  React.useEffect(() => {
    const id = window.setInterval(() => {
      setSpark((prev) => [...prev.slice(1), 6 + Math.random() * 20]);
    }, 1600);
    return () => window.clearInterval(id);
  }, []);

  function newTask() {
    createConversation("agent");
  }
  function newProject() {
    const id = createProject(t("project.untitled"));
    openProjects(id);
  }

  const dockPlugins = DOCK_PLUGIN_IDS.map((id) => PLUGINS.find((p) => p.id === id)!).filter(Boolean);

  return (
    <aside
      aria-label={t("dock.title")}
      className="hidden w-72 shrink-0 flex-col gap-3 overflow-y-auto border-l border-sidebar-border bg-sidebar p-3 xl:flex"
    >
      <section className="nexa-glass space-y-3 rounded-2xl p-3">
        <p className="text-[10px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">
          {t("dock.activeModel")}
        </p>
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-lg bg-amber-500/15 text-amber-300">
            <Crown className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{modelLabel}</p>
            <p className="text-[11px] text-muted-foreground">{t("dock.modelReady")}</p>
          </div>
        </div>
        <Sparkline points={spark} />
        <button
          type="button"
          onClick={() => openSettings("models")}
          className="w-full rounded-lg bg-primary/15 px-2 py-1.5 text-xs font-medium text-primary hover:bg-primary/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {t("settings.models")}
        </button>
      </section>

      <section className="nexa-glass space-y-2 rounded-2xl p-3">
        <p className="text-[10px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">
          {t("dock.quickActions")}
        </p>
        <div className="grid grid-cols-2 gap-2">
          {[
            { id: "task", icon: ListTodo, label: t("dock.newTask"), onClick: newTask },
            { id: "upload", icon: FileUp, label: t("dock.uploadFile"), onClick: () => fileInputRef.current?.click() },
            { id: "project", icon: FolderKanban, label: t("dock.createProject"), onClick: newProject },
            { id: "knowledge", icon: BookOpen, label: t("dock.openKnowledge"), onClick: () => openSettings("knowledge") },
          ].map((action) => (
            <button
              key={action.id}
              type="button"
              onClick={action.onClick}
              className="flex flex-col items-start gap-2 rounded-xl border border-border/60 bg-background/20 px-2.5 py-2.5 text-left text-xs hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <action.icon className="size-4 text-primary" aria-hidden="true" />
              <span className="leading-tight">{action.label}</span>
            </button>
          ))}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={() => openSettings("knowledge")}
        />
      </section>

      <section className="nexa-glass space-y-3 rounded-2xl p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[10px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">
            {t("dock.plugins")}
          </p>
          <button
            type="button"
            onClick={() => openSettings("plugins")}
            className="text-[11px] text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {t("settings.plugins")}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {dockPlugins.map((plugin) => {
            const isOn = enabled[plugin.id] ?? true;
            const Icon =
              plugin.id === "web_search"
                ? Globe
                : plugin.id === "calculator"
                  ? Sparkles
                  : plugin.id === "file_system"
                    ? FolderKanban
                    : Code2;
            return (
              <Tooltip key={plugin.id}>
                <TooltipTrigger
                  render={
                    <button
                      type="button"
                      onClick={() => setPlugin(plugin.id, !isOn)}
                      aria-pressed={isOn}
                      aria-label={t(`plugins.${plugin.id}.name`)}
                      className={cn(
                        "relative flex size-11 items-center justify-center rounded-xl border transition-all",
                        isOn
                          ? "border-primary/50 bg-primary/20 text-foreground shadow-[0_0_18px_-6px_var(--nexa-violet)]"
                          : "border-border/50 bg-background/30 text-muted-foreground opacity-55"
                      )}
                    >
                      <Icon className="size-5" aria-hidden="true" />
                    </button>
                  }
                />
                <TooltipContent>
                  {`${t(`plugins.${plugin.id}.name`)} — ${isOn ? t("dock.pluginOn") : t("dock.pluginOff")}`}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </section>

      <section className="nexa-glass mt-auto space-y-3 rounded-2xl p-3">
        <p className="text-[10px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">
          {t("dock.systemMonitor")}
        </p>
        <div className="space-y-2.5">
          <MonitorBar label="CPU" valueLabel={`${Math.round(cpu)}%`} value={cpu} />
          <MonitorBar
            label="RAM"
            valueLabel={`${Math.round(ramUsed)}% / ${Math.round(ramAvail)}%`}
            value={ramUsed}
          />
        </div>
      </section>
    </aside>
  );
}

function MonitorBar({ label, value, valueLabel }: { label: string; value: number; valueLabel: string }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">{valueLabel}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-background/40">
        <div
          className="h-full rounded-full nexa-gradient-chat transition-[width] duration-700"
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
    </div>
  );
}

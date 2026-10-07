"use client";
import * as React from "react";
import { LogoMark } from "@/components/common/logo";
import { useT } from "@/lib/i18n";
import {
  getDesktopAppInfo,
  getDesktopBackendStatus,
  isDesktopApp,
  type NexaAppInfo,
  type NexaBackendStatus,
} from "@/lib/electron-bridge";
export function AboutSection() {
  const t = useT();
  const [appInfo, setAppInfo] = React.useState<NexaAppInfo | null>(null);
  const [backendStatus, setBackendStatus] = React.useState<NexaBackendStatus | null>(null);
  React.useEffect(() => {
    void getDesktopAppInfo().then(setAppInfo);
    void getDesktopBackendStatus().then(setBackendStatus);
  }, []);
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-xl nexa-gradient-bg">
          <LogoMark className="size-6" />
        </div>
        <div>
          <p className="font-semibold">{t("chat.emptyTitle")}</p>
          <p className="text-sm text-muted-foreground italic">{t("chat.emptyTagline")}</p>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">{t("about.desc")}</p>
      <p className="text-sm text-muted-foreground">{t("about.frontendSep")}</p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-border p-3 text-sm">
        <dt className="text-muted-foreground">{isDesktopApp() ? t("about.desktopApp") : t("about.browserApp")}</dt>
        <dd className="font-medium">{appInfo ? `${appInfo.platform}` : "—"}</dd>
        {appInfo && (
          <>
            <dt className="text-muted-foreground">{t("about.version")}</dt>
            <dd className="font-medium">{appInfo.version}</dd>
          </>
        )}
        {backendStatus && (
          <>
            <dt className="text-muted-foreground">{t("about.backend")}</dt>
            <dd className="font-medium">
              {backendStatus.reachable ? t("about.backendReachable") : t("about.backendUnreachable")}
            </dd>
          </>
        )}
      </dl>
    </div>
  );
}

"use client";

import * as React from "react";
import { getHealth } from "@/lib/api";
import { useT } from "@/lib/i18n";

/** Honest warning when the backend runs on ephemeral free-tier storage. */
export function StorageModeBanner() {
  const t = useT();
  const [ephemeral, setEphemeral] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    void getHealth()
      .then((h) => {
        if (!cancelled && h.storage_mode === "ephemeral") setEphemeral(true);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  if (!ephemeral) return null;

  return (
    <div
      role="status"
      className="shrink-0 border-b border-amber-500/40 bg-amber-500/10 px-3 py-2 text-center text-xs text-amber-950 dark:text-amber-100"
    >
      {t("storage.ephemeralBanner")}
    </div>
  );
}

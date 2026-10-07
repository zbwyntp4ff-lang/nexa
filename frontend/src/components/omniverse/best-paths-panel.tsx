"use client";
import * as React from "react";
import { useT } from "@/lib/i18n";
import type { OmniNode } from "@/lib/omniverse/types";
import { useOmniverseStore } from "@/store/omniverse-store";

function pickBestPaths(nodes: OmniNode[]): OmniNode[] {
  return nodes
    .filter(
      (n) =>
        n.kind === "BEST_PATH" ||
        (n.status === "PROMISING" && (n.kind === "HYPOTHESIS" || n.kind === "CROSSOVER"))
    )
    .sort((a, b) => b.score.overall - a.score.overall)
    .slice(0, 5);
}

export function OmniverseBestPaths() {
  const t = useT();
  const map = useOmniverseStore((s) => s.map);
  const selectNode = useOmniverseStore((s) => s.selectNode);
  // Derive in useMemo from stable `map` — calling getBestPaths() inside the
  // zustand selector returned a fresh array every time and infinite-looped.
  const paths = React.useMemo(() => (map ? pickBestPaths(map.nodes) : []), [map]);
  if (paths.length === 0) return null;
  return (
    <div className="nexa-glass absolute bottom-3 left-3 z-10 w-[min(22rem,calc(100%-1.5rem))] rounded-2xl p-3">
      <p className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
        {t("omniverse.bestPaths")}
      </p>
      <ul className="mt-2 space-y-1.5">
        {paths.map((p, i) => (
          <li key={p.id}>
            <button
              type="button"
              onClick={() => selectNode(p.id)}
              className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left text-xs hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md bg-primary/20 text-[10px] font-bold text-primary">
                {i + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 font-medium">{p.kind === "BEST_PATH" ? p.summary : p.title}</span>
                <span className="mt-0.5 block text-[10px] text-muted-foreground">
                  {p.status} · overall {p.score.overall}
                  {p.rejectedReason ? ` · ${t("omniverse.keptRejected")}` : ""}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

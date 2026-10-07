"use client";
import * as React from "react";
import { kindColor } from "@/lib/omniverse/explore-engine";
import type { OmniEdge, OmniNode } from "@/lib/omniverse/types";
import { cn } from "@/lib/utils";
import { useOmniverseStore } from "@/store/omniverse-store";

const NODE_W = 168;
const NODE_H = 64;
const WORLD = 2400;

function statusClass(status: string): string {
  switch (status) {
    case "PROMISING":
      return "border-emerald-400/70 bg-emerald-500/15";
    case "VALIDATED":
      return "border-sky-400/70 bg-sky-500/15";
    case "TESTING":
    case "RESEARCHING":
      return "border-amber-400/70 bg-amber-500/15";
    case "REJECTED":
      return "border-rose-400/60 bg-rose-500/10 opacity-80";
    default:
      return "border-border/70 bg-card/80";
  }
}

export function OmniverseGraph() {
  const map = useOmniverseStore((s) => s.map);
  const camera = useOmniverseStore((s) => s.camera);
  const setCamera = useOmniverseStore((s) => s.setCamera);
  const selectedId = useOmniverseStore((s) => s.selectedId);
  const selectNode = useOmniverseStore((s) => s.selectNode);
  const toggleExpand = useOmniverseStore((s) => s.toggleExpand);
  const crossoverSelection = useOmniverseStore((s) => s.crossoverSelection);
  const toggleCrossoverPick = useOmniverseStore((s) => s.toggleCrossoverPick);
  const getVisibleNodes = useOmniverseStore((s) => s.getVisibleNodes);
  const nodes = getVisibleNodes();
  const visibleIds = new Set(nodes.map((n) => n.id));
  const edges = (map?.edges ?? []).filter((e) => visibleIds.has(e.from) && visibleIds.has(e.to));
  const nodeById = new Map((map?.nodes ?? []).map((n) => [n.id, n]));

  const dragRef = React.useRef<{ px: number; py: number; cx: number; cy: number } | null>(null);
  const [, setTick] = React.useState(0);

  React.useEffect(() => {
    // Appear animation only — keep this slow enough that React 19 does not
    // treat rapid setState as a maximum-update-depth loop (#185).
    const id = window.setInterval(() => setTick((t) => t + 1), 500);
    return () => window.clearInterval(id);
  }, []);

  function onWheel(e: React.WheelEvent) {
    e.preventDefault();
    const next = Math.min(2.2, Math.max(0.35, camera.zoom * (e.deltaY > 0 ? 0.92 : 1.08)));
    setCamera({ zoom: next });
  }

  function onPointerDown(e: React.PointerEvent) {
    if ((e.target as HTMLElement).closest("[data-omni-node]")) return;
    dragRef.current = { px: e.clientX, py: e.clientY, cx: camera.x, cy: camera.y };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent) {
    const d = dragRef.current;
    if (!d) return;
    setCamera({
      x: d.cx + (e.clientX - d.px),
      y: d.cy + (e.clientY - d.py),
    });
  }
  function onPointerUp() {
    dragRef.current = null;
  }

  return (
    <div
      className="relative h-full min-h-0 w-full cursor-grab overflow-hidden active:cursor-grabbing"
      onWheel={onWheel}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <div
        className="absolute left-1/2 top-1/2 origin-center will-change-transform"
        style={{
          width: WORLD,
          height: WORLD,
          marginLeft: -WORLD / 2,
          marginTop: -WORLD / 2,
          transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.zoom})`,
        }}
      >
        <svg
          className="pointer-events-none absolute inset-0"
          width={WORLD}
          height={WORLD}
          viewBox={`${-WORLD / 2} ${-WORLD / 2} ${WORLD} ${WORLD}`}
        >
          {edges.map((edge) => (
            <EdgeLine key={edge.id} edge={edge} from={nodeById.get(edge.from)} to={nodeById.get(edge.to)} />
          ))}
        </svg>
        {nodes.map((node) => {
          const age = Date.now() - node.bornAt;
          const appear = Math.min(1, age / 450);
          const selected = selectedId === node.id;
          const picked = crossoverSelection.includes(node.id);
          return (
            <button
              key={node.id}
              type="button"
              data-omni-node
              onClick={(e) => {
                e.stopPropagation();
                if (e.shiftKey) toggleCrossoverPick(node.id);
                else selectNode(node.id);
              }}
              onDoubleClick={(e) => {
                e.stopPropagation();
                toggleExpand(node.id);
              }}
              className={cn(
                "absolute flex flex-col items-start justify-center rounded-xl border px-3 py-2 text-left shadow-md backdrop-blur-md transition-[opacity,transform] duration-300",
                statusClass(node.status),
                selected && "ring-2 ring-primary",
                picked && "outline outline-2 outline-offset-2 outline-[var(--mode-create)]"
              )}
              style={{
                width: NODE_W,
                height: NODE_H,
                left: WORLD / 2 + node.x - NODE_W / 2,
                top: WORLD / 2 + node.y - NODE_H / 2,
                opacity: appear,
                transform: `scale(${0.85 + appear * 0.15})`,
                borderColor: kindColor(node.kind),
              }}
            >
              <span className="text-[9px] font-semibold tracking-wider uppercase opacity-70">
                {node.kind.replace("_", " ")}
              </span>
              <span className="line-clamp-2 text-xs font-medium leading-snug">{node.title}</span>
              <span className="mt-0.5 text-[10px] tabular-nums opacity-70">
                {node.status} · {node.score.overall}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function EdgeLine({ edge, from, to }: { edge: OmniEdge; from?: OmniNode; to?: OmniNode }) {
  if (!from || !to) return null;
  const x1 = from.x;
  const y1 = from.y;
  const x2 = to.x;
  const y2 = to.y;
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2 - 36;
  const stroke =
    edge.kind === "crossover"
      ? "var(--mode-create)"
      : edge.kind === "best"
        ? "var(--mode-vision)"
        : "color-mix(in oklch, var(--foreground), transparent 65%)";
  return (
    <path
      d={`M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`}
      fill="none"
      stroke={stroke}
      strokeWidth={edge.kind === "crossover" ? 2.2 : 1.4}
      strokeDasharray={edge.kind === "best" ? "5 4" : undefined}
      opacity={0.85}
    />
  );
}

import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GameCreatorPanel } from "@/components/game-creator/game-creator-panel";
import { isThreeBuild, useGameCreatorStore } from "@/store/game-creator-store";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getBuildProject: vi.fn(async () => ({
      project_id: "p1",
      slug: "three-racing",
      title: "NEXA Racing 3D",
      status: "READY",
      entry_file: "index.html",
      files: ["index.html", "main.js", "style.css", "scene.json", "README.md"],
      preview_url: "/api/v1/build/preview/p1/index.html",
      stack: "HTML / CSS / JS (Three.js CDN 3D)",
      features: ["гонка"],
      root_rel: "builds/x",
    })),
    fetchBuildPreviewText: vi.fn(async (_id: string, file: string) =>
      file === "scene.json" ? '{"engine":"three.js","genre":"racing"}' : `// ${file}`,
    ),
    runBuild: vi.fn(),
  };
});

describe("isThreeBuild", () => {
  it("detects scene.json and Three.js stack", () => {
    expect(isThreeBuild({ files: ["scene.json"] })).toBe(true);
    expect(isThreeBuild({ stack: "HTML / CSS / JS (Three.js CDN 3D)" })).toBe(true);
    expect(isThreeBuild({ message: "создай 3d гонку" })).toBe(true);
    expect(isThreeBuild({ files: ["index.html"], stack: "canvas", message: "сайт" })).toBe(false);
  });
});

describe("GameCreatorPanel", () => {
  beforeEach(() => {
    useGameCreatorStore.setState({
      open: false,
      projectId: null,
      previewUrl: null,
      previewRunning: true,
      previewKey: 0,
      consoleLines: [],
      files: [],
      sceneJson: null,
      fileContent: "",
    });
  });

  it("mounts sandboxed preview and stop clears iframe", async () => {
    const user = userEvent.setup();
    act(() => {
      useGameCreatorStore.getState().openGameCreator({
        projectId: "p1",
        previewUrl: "/api/v1/build/preview/p1/index.html",
        title: "NEXA Racing 3D",
        files: ["index.html", "main.js", "scene.json"],
        stack: "Three.js",
      });
    });
    render(<GameCreatorPanel />);
    const iframe = await screen.findByTitle(/game preview|превью игры/i);
    expect(iframe).toHaveAttribute("sandbox");
    const sandbox = iframe.getAttribute("sandbox") || "";
    expect(sandbox).toContain("allow-scripts");
    expect(sandbox).not.toContain("allow-same-origin");

    await user.click(screen.getByRole("button", { name: /stop|стоп/i }));
    expect(screen.queryByTitle(/game preview|превью игры/i)).toBeNull();
    expect(screen.getByText(/preview stopped|превью остановлено/i)).toBeInTheDocument();
  });
});

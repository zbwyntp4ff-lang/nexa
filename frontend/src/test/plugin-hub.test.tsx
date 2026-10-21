import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PluginHub } from "@/components/settings/sections/plugin-hub";
import { PluginsSection } from "@/components/settings/sections/plugins-section";

const { listHubPluginsMock, getHubPluginMock, connectHubPluginMock, disconnectHubPluginMock } = vi.hoisted(
  () => ({
    listHubPluginsMock: vi.fn(),
    getHubPluginMock: vi.fn(),
    connectHubPluginMock: vi.fn(),
    disconnectHubPluginMock: vi.fn(),
  }),
);

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listHubPlugins: listHubPluginsMock,
    getHubPlugin: getHubPluginMock,
    connectHubPlugin: connectHubPluginMock,
    disconnectHubPlugin: disconnectHubPluginMock,
    diagnoseHubPlugin: vi.fn(),
    invokeHubPlugin: vi.fn(),
    patchHubPluginPermissions: vi.fn(),
  };
});

function card(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "vscode",
    version: "1.0.0",
    name: "VS Code",
    description: "Open a permitted project folder",
    category: "editor",
    integration_type: "local",
    dependencies: ["Visual Studio Code"],
    required_permissions: ["files.read"],
    optional_permissions: ["files.write"],
    timeout_seconds: 20,
    actions: [{ name: "list", description: "List files", permissions: ["files.read"], dangerous: false, input_schema: {} }],
    install_hint: "Install VS Code",
    status: "disconnected",
    enabled: false,
    granted_permissions: [],
    settings: {},
    has_token: false,
    last_error: null,
    last_probe: null,
    connected_at: null,
    ...overrides,
  };
}

describe("Plugin Hub", () => {
  it("lists plugins and opens details", async () => {
    listHubPluginsMock.mockResolvedValue({ plugins: [card()], count: 1 });
    getHubPluginMock.mockResolvedValue(card());
    render(<PluginHub />);
    expect(await screen.findByText("Plugin Hub")).toBeInTheDocument();
    expect(await screen.findByText("VS Code")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /VS Code/i }));
    expect(await screen.findByRole("button", { name: /^(Connect|Подключить)$/i })).toBeInTheDocument();
    expect(screen.getByText(/files.read/)).toBeInTheDocument();
  });

  it("connects only after API reports enabled", async () => {
    listHubPluginsMock.mockResolvedValue({ plugins: [card()], count: 1 });
    getHubPluginMock.mockResolvedValue(card());
    connectHubPluginMock.mockResolvedValue(card({ enabled: true, status: "connected_limited" }));
    render(<PluginHub />);
    await userEvent.click(await screen.findByRole("button", { name: /VS Code/i }));
    await userEvent.click(await screen.findByRole("button", { name: /^(Connect|Подключить)$/i }));
    await waitFor(() => expect(connectHubPluginMock).toHaveBeenCalled());
  });
});

describe("Plugins settings section", () => {
  it("keeps built-in capability toggles and the hub", async () => {
    listHubPluginsMock.mockResolvedValue({ plugins: [], count: 0 });
    render(<PluginsSection />);
    expect(screen.getByText("Plugins")).toBeInTheDocument();
    expect(screen.getByText("Web Search")).toBeInTheDocument();
    expect(await screen.findByText("Plugin Hub")).toBeInTheDocument();
  });
});

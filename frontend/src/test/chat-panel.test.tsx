import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ApiError } from "@/lib/api";
import { useChatStore } from "@/store/chat-store";
import { useUiStore } from "@/store/ui-store";
const { sendChatMock } = vi.hoisted(() => ({ sendChatMock: vi.fn() }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    sendChat: sendChatMock,
  };
});
function resetStores() {
  useChatStore.setState({ conversations: [], activeConversationId: null, projects: [] });
  useUiStore.setState({
    mobileDrawerOpen: false,
    desktopSidebarCollapsed: false,
    settingsOpen: false,
    settingsSection: "general",
    projectsOpen: false,
    activeProjectId: null,
    status: "offline",
    activeTool: null,
    pendingMode: "chat",
  });
}
describe("ChatPanel (Chat mode end-to-end)", () => {
  beforeEach(() => {
    resetStores();
    sendChatMock.mockReset();
  });
  it("shows the empty state with suggestions when there is no active conversation", () => {
    render(<ChatPanel />);
    expect(screen.getByText("NEXA AI")).toBeInTheDocument();
    expect(screen.getByText("Think. Create. Act.")).toBeInTheDocument();
  });
  it("creates a conversation and sends a message, then renders the real response", async () => {
    sendChatMock.mockResolvedValue({
      message: "[mock:nexa-mock-1] You said: Hello NEXA",
      provider: "mock",
      model: "nexa-mock-1",
      latency_ms: 1.2,
      created_at: new Date().toISOString(),
    });
    const user = userEvent.setup();
    render(<ChatPanel />);
    const textarea = screen.getByLabelText("Message NEXA");
    await user.type(textarea, "Hello NEXA{Enter}");
    expect(screen.getByText("Hello NEXA")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("[mock:nexa-mock-1] You said: Hello NEXA")).toBeInTheDocument()
    );
    expect(sendChatMock).toHaveBeenCalledTimes(1);
    expect(useChatStore.getState().conversations).toHaveLength(1);
  });
  it("shows a Thinking status while the request is in flight", async () => {
    let resolveResponse: (value: unknown) => void = () => {};
    sendChatMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveResponse = resolve;
        })
    );
    const user = userEvent.setup();
    render(<ChatPanel />);
    await user.type(screen.getByLabelText("Message NEXA"), "Hello{Enter}");
    await waitFor(() => expect(screen.getByText("Thinking…")).toBeInTheDocument());
    resolveResponse({
      message: "done",
      provider: "mock",
      model: "nexa-mock-1",
      latency_ms: 1,
      created_at: new Date().toISOString(),
    });
    await waitFor(() => expect(screen.queryByText("Thinking…")).not.toBeInTheDocument());
  });
  // --- Error state -------------------------------------------------------------
  it("shows an error message when the backend request fails", async () => {
    sendChatMock.mockRejectedValue(new ApiError(503, "ProviderConfigurationError", "Provider is not configured correctly."));
    const user = userEvent.setup();
    render(<ChatPanel />);
    await user.type(screen.getByLabelText("Message NEXA"), "Hello{Enter}");
    await waitFor(() =>
      expect(screen.getByText("Provider is not configured correctly.")).toBeInTheDocument()
    );
    expect(useUiStore.getState().status).toBe("error");
  });
  it("shows a generic error message for network failures", async () => {
    sendChatMock.mockRejectedValue(new ApiError(0, "NetworkError", "Could not reach the NEXA backend. Is it running?"));
    const user = userEvent.setup();
    render(<ChatPanel />);
    await user.type(screen.getByLabelText("Message NEXA"), "Hello{Enter}");
    await waitFor(() =>
      expect(screen.getByText("Could not reach the NEXA backend. Is it running?")).toBeInTheDocument()
    );
  });
  it("allows retrying after an error", async () => {
    sendChatMock
      .mockRejectedValueOnce(new ApiError(502, "ModelError", "The model failed to generate a response."))
      .mockResolvedValueOnce({
        message: "Recovered response",
        provider: "mock",
        model: "nexa-mock-1",
        latency_ms: 1,
        created_at: new Date().toISOString(),
      });
    const user = userEvent.setup();
    render(<ChatPanel />);
    await user.type(screen.getByLabelText("Message NEXA"), "Hello{Enter}");
    await waitFor(() => expect(screen.getByText("The model failed to generate a response.")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByText("Recovered response")).toBeInTheDocument());
    expect(sendChatMock).toHaveBeenCalledTimes(2);
  });
  it("uses the suggestion buttons on the empty state to start a conversation", async () => {
    sendChatMock.mockResolvedValue({
      message: "ok",
      provider: "mock",
      model: "nexa-mock-1",
      latency_ms: 1,
      created_at: new Date().toISOString(),
    });
    const user = userEvent.setup();
    render(<ChatPanel />);
    const suggestion = screen.getAllByRole("button")[0];
    await user.click(suggestion);
    await waitFor(() => expect(useChatStore.getState().conversations).toHaveLength(1));
  });
});

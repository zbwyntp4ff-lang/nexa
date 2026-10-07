import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SidebarContent } from "@/components/layout/sidebar/sidebar-content";
import { useChatStore } from "@/store/chat-store";
import { useUiStore } from "@/store/ui-store";
function resetStores() {
  useChatStore.setState({ conversations: [], activeConversationId: null, projects: [] });
  useUiStore.setState({
    mobileDrawerOpen: false,
    desktopSidebarCollapsed: false,
    settingsOpen: false,
    settingsSection: "general",
    projectsOpen: false,
    activeProjectId: null,
    workflowsOpen: false,
    status: "offline",
    activeTool: null,
    pendingMode: "chat",
  });
}
describe("Sidebar", () => {
  beforeEach(() => {
    resetStores();
  });
  it("shows an empty state when there are no chats yet", () => {
    render(<SidebarContent />);
    expect(screen.getByText(/no chats yet/i)).toBeInTheDocument();
  });
  it("creates a new chat when 'New chat' is clicked", async () => {
    const user = userEvent.setup();
    render(<SidebarContent />);
    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(useChatStore.getState().conversations).toHaveLength(1);
    expect(useChatStore.getState().activeConversationId).toBe(useChatStore.getState().conversations[0].id);
  });
  it("lists existing conversations under Recent chats", () => {
    useChatStore.getState().createConversation("chat");
    useChatStore.getState().renameConversation(useChatStore.getState().conversations[0].id, "My first chat");
    render(<SidebarContent />);
    expect(screen.getByText("My first chat")).toBeInTheDocument();
  });
  it("switches the active conversation when a chat is clicked", async () => {
    const user = userEvent.setup();
    const firstId = useChatStore.getState().createConversation("chat");
    useChatStore.getState().renameConversation(firstId, "First");
    const secondId = useChatStore.getState().createConversation("chat");
    useChatStore.getState().renameConversation(secondId, "Second");
    // creating "second" made it active; explicitly re-activate "first" to test switching.
    useChatStore.getState().setActiveConversation(secondId);
    render(<SidebarContent />);
    await user.click(screen.getByText("First"));
    expect(useChatStore.getState().activeConversationId).toBe(firstId);
  });
  it("filters chats by the search box", async () => {
    const user = userEvent.setup();
    const id1 = useChatStore.getState().createConversation("chat");
    useChatStore.getState().renameConversation(id1, "Talk about apples");
    const id2 = useChatStore.getState().createConversation("chat");
    useChatStore.getState().renameConversation(id2, "Talk about oranges");
    render(<SidebarContent />);
    await user.type(screen.getByLabelText("Search chat history"), "apples");
    expect(screen.getByText("Talk about apples")).toBeInTheDocument();
    expect(screen.queryByText("Talk about oranges")).not.toBeInTheDocument();
  });
  it("renames a conversation via the dropdown menu", async () => {
    const user = userEvent.setup();
    const id = useChatStore.getState().createConversation("chat");
    useChatStore.getState().renameConversation(id, "Old title");
    render(<SidebarContent />);
    await user.click(screen.getByRole("button", { name: /more actions for old title/i }));
    await user.click(await screen.findByRole("menuitem", { name: "Edit" }));
    const input = screen.getByLabelText("Rename chat");
    await user.clear(input);
    await user.type(input, "New title{Enter}");
    await waitFor(() => expect(useChatStore.getState().conversations[0].title).toBe("New title"));
  });
  it("deletes a conversation after confirming in the alert dialog", async () => {
    const user = userEvent.setup();
    const id = useChatStore.getState().createConversation("chat");
    useChatStore.getState().renameConversation(id, "Delete me");
    render(<SidebarContent />);
    await user.click(screen.getByRole("button", { name: /more actions for delete me/i }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(useChatStore.getState().conversations).toHaveLength(0));
  });
  it("does not delete a conversation if the confirmation is cancelled", async () => {
    const user = userEvent.setup();
    const id = useChatStore.getState().createConversation("chat");
    useChatStore.getState().renameConversation(id, "Keep me");
    render(<SidebarContent />);
    await user.click(screen.getByRole("button", { name: /more actions for keep me/i }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(useChatStore.getState().conversations).toHaveLength(1);
  });
  it("creates a new project when the project '+' button is clicked", async () => {
    const user = userEvent.setup();
    render(<SidebarContent />);
    await user.click(screen.getByRole("button", { name: "New project" }));
    expect(useChatStore.getState().projects).toHaveLength(1);
    expect(useUiStore.getState().projectsOpen).toBe(true);
  });
  it("opens Settings when the Settings button is clicked", async () => {
    const user = userEvent.setup();
    render(<SidebarContent />);
    await user.click(screen.getByRole("button", { name: "Settings" }));
    expect(useUiStore.getState().settingsOpen).toBe(true);
  });
  it("calls onNavigate after selecting a chat (used to close the mobile drawer)", async () => {
    const user = userEvent.setup();
    const id = useChatStore.getState().createConversation("chat");
    useChatStore.getState().renameConversation(id, "Some chat");
    const onNavigate = vi.fn();
    render(<SidebarContent onNavigate={onNavigate} />);
    await user.click(screen.getByText("Some chat"));
    expect(onNavigate).toHaveBeenCalled();
  });
});

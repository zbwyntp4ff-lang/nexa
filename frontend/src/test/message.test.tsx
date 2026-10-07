import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Message } from "@/components/chat/message";
import type { ChatMessageView } from "@/lib/types";
function baseMessage(overrides: Partial<ChatMessageView> = {}): ChatMessageView {
  return {
    id: "m1",
    role: "assistant",
    content: "Hello there",
    createdAt: new Date().toISOString(),
    mode: "chat",
    ...overrides,
  };
}
describe("Message", () => {
  it("renders a user message as plain text", () => {
    render(
      <Message
        message={baseMessage({ role: "user", content: "Hi NEXA" })}
        onRetry={vi.fn()}
        onEdit={vi.fn()}
        onStop={vi.fn()}
      />
    );
    expect(screen.getByText("Hi NEXA")).toBeInTheDocument();
    expect(screen.getAllByText("You").length).toBeGreaterThan(0);
  });
  it("renders an assistant message as markdown", () => {
    render(
      <Message
        message={baseMessage({ content: "**bold text**" })}
        onRetry={vi.fn()}
        onEdit={vi.fn()}
        onStop={vi.fn()}
      />
    );
    expect(screen.getByText("bold text").tagName).toBe("STRONG");
  });
  // --- Loading state ---------------------------------------------------------
  it("shows a loading indicator for a pending message", () => {
    render(
      <Message message={baseMessage({ pending: true, content: "" })} onRetry={vi.fn()} onEdit={vi.fn()} onStop={vi.fn()} />
    );
    expect(screen.getByText("Thinking…")).toBeInTheDocument();
  });
  it("shows streamed text and a typing indicator while a reply is still arriving", () => {
    render(
      <Message message={baseMessage({ pending: true, content: "25 * 37 = 925" })} onRetry={vi.fn()} onEdit={vi.fn()} onStop={vi.fn()} />
    );
    expect(screen.getByText("25 * 37 = 925")).toBeInTheDocument();
    expect(screen.getByText("Typing...")).toBeInTheDocument();
  });
  it("shows a Stop button while pending, instead of Copy/Regenerate", () => {
    render(
      <Message message={baseMessage({ pending: true, content: "" })} onRetry={vi.fn()} onEdit={vi.fn()} onStop={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: "Stop generating" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy" })).not.toBeInTheDocument();
  });
  it("calls onStop when Stop is clicked on a pending message", async () => {
    const user = userEvent.setup();
    const onStop = vi.fn();
    render(<Message message={baseMessage({ pending: true, content: "" })} onRetry={vi.fn()} onEdit={vi.fn()} onStop={onStop} />);
    await user.click(screen.getByRole("button", { name: "Stop generating" }));
    expect(onStop).toHaveBeenCalledTimes(1);
  });
  // --- Error state -------------------------------------------------------------
  it("shows the error message when a message has an error", () => {
    render(
      <Message
        message={baseMessage({ content: "", error: "The NEXA backend is unreachable." })}
        onRetry={vi.fn()}
        onEdit={vi.fn()}
        onStop={vi.fn()}
      />
    );
    expect(screen.getByText("The NEXA backend is unreachable.")).toBeInTheDocument();
  });
  it("labels the regenerate action 'Retry' for an errored message", () => {
    render(
      <Message
        message={baseMessage({ content: "", error: "Something failed." })}
        onRetry={vi.fn()}
        onEdit={vi.fn()}
        onStop={vi.fn()}
      />
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
  it("calls onRetry when Retry is clicked", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <Message
        message={baseMessage({ content: "", error: "Something failed." })}
        onRetry={onRetry}
        onEdit={vi.fn()}
        onStop={vi.fn()}
      />
    );
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
  // --- Editing / Copy --------------------------------------------------------
  it("lets the user edit and resubmit their own message", async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    render(<Message message={baseMessage({ role: "user", content: "Original" })} onRetry={vi.fn()} onEdit={onEdit} onStop={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const textarea = screen.getByLabelText("Edit message");
    await user.clear(textarea);
    await user.type(textarea, "Edited message");
    await user.click(screen.getByRole("button", { name: "Save & submit" }));
    expect(onEdit).toHaveBeenCalledWith("Edited message");
  });
  it("copies the message content to the clipboard", async () => {
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<Message message={baseMessage({ content: "Copy me" })} onRetry={vi.fn()} onEdit={vi.fn()} onStop={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith("Copy me");
  });
  it("renders agent tool-call steps for assistant messages", () => {
    render(
      <Message
        message={baseMessage({
          content: "Done.",
          agentSteps: [
            {
              index: 0,
              stepType: "tool_call",
              toolName: "calculator",
              toolInput: { expression: "2 + 2" },
              output: 4,
              success: true,
              error: null,
              dryRun: false,
            },
          ],
        })}
        onRetry={vi.fn()}
        onEdit={vi.fn()}
        onStop={vi.fn()}
      />
    );
    expect(screen.getByText("calculator")).toBeInTheDocument();
  });
});

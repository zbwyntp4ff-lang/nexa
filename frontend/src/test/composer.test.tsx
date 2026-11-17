import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { Composer } from "@/components/chat/composer";
vi.mock("sonner", () => ({ toast: vi.fn() }));
const { uploadAttachmentMock } = vi.hoisted(() => ({ uploadAttachmentMock: vi.fn() }));
vi.mock("@/lib/attachments", async () => {
  const actual = await vi.importActual<typeof import("@/lib/attachments")>("@/lib/attachments");
  return {
    ...actual,
    uploadAttachment: uploadAttachmentMock,
    deleteAttachmentBestEffort: vi.fn(),
  };
});
describe("Composer (input area)", () => {
  it("shows the 'Ask NEXA...' placeholder", () => {
    render(<Composer onSend={vi.fn()} onStop={vi.fn()} isSending={false} />);
    expect(screen.getByPlaceholderText("Ask NEXA...")).toBeInTheDocument();
  });
  it("sends the message when Enter is pressed", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<Composer onSend={onSend} onStop={vi.fn()} isSending={false} />);
    const textarea = screen.getByLabelText("Message NEXA");
    await user.type(textarea, "Hello NEXA{Enter}");
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith("Hello NEXA", undefined);
  });
  it("uses Ctrl+Enter when Enter-to-send is disabled", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const { useUiStore } = await import("@/store/ui-store");
    useUiStore.getState().setEnterToSend(false);
    render(<Composer onSend={onSend} onStop={vi.fn()} isSending={false} />);
    const textarea = screen.getByLabelText("Message NEXA");
    await user.type(textarea, "line one{Enter}line two");
    expect(onSend).not.toHaveBeenCalled();
    await user.keyboard("{Control>}{Enter}{/Control}");
    expect(onSend).toHaveBeenCalledWith("line one\nline two", undefined);
    useUiStore.getState().setEnterToSend(true);
  });
  it("does not send and inserts a newline when Shift+Enter is pressed", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<Composer onSend={onSend} onStop={vi.fn()} isSending={false} />);
    const textarea = screen.getByLabelText("Message NEXA") as HTMLTextAreaElement;
    await user.type(textarea, "line one{Shift>}{Enter}{/Shift}line two");
    expect(onSend).not.toHaveBeenCalled();
    expect(textarea.value).toBe("line one\nline two");
  });
  it("does not send an empty message", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<Composer onSend={onSend} onStop={vi.fn()} isSending={false} />);
    const textarea = screen.getByLabelText("Message NEXA");
    await user.type(textarea, "{Enter}");
    expect(onSend).not.toHaveBeenCalled();
    // The send button is disabled too when there's nothing to send.
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });
  it("clears the input after sending", async () => {
    const user = userEvent.setup();
    render(<Composer onSend={vi.fn()} onStop={vi.fn()} isSending={false} />);
    const textarea = screen.getByLabelText("Message NEXA") as HTMLTextAreaElement;
    await user.type(textarea, "Hello{Enter}");
    expect(textarea.value).toBe("");
  });
  it("shows a Stop button instead of Send while a request is in flight", () => {
    render(<Composer onSend={vi.fn()} onStop={vi.fn()} isSending />);
    expect(screen.getByRole("button", { name: "Stop generating" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send message" })).not.toBeInTheDocument();
  });
  it("calls onStop when the Stop button is clicked", async () => {
    const user = userEvent.setup();
    const onStop = vi.fn();
    render(<Composer onSend={vi.fn()} onStop={onStop} isSending />);
    await user.click(screen.getByRole("button", { name: "Stop generating" }));
    expect(onStop).toHaveBeenCalledTimes(1);
  });
  it("opens HEXA voice chat when the mic button is clicked", async () => {
    const user = userEvent.setup();
    const setActiveView = vi.fn();
    const ui = await import("@/store/ui-store");
    const spy = vi.spyOn(ui.useUiStore, "getState").mockReturnValue({
      ...ui.useUiStore.getState(),
      setActiveView,
    } as ReturnType<typeof ui.useUiStore.getState>);
    render(<Composer onSend={vi.fn()} onStop={vi.fn()} isSending={false} />);
    await user.click(screen.getByRole("button", { name: "Voice input (HEXA)" }));
    expect(setActiveView).toHaveBeenCalledWith("hexa");
    spy.mockRestore();
  });
  // --- File upload UI (Part 8: real backend upload, not client-only reading) ---
  it("uploads and shows an attachment chip when a document is selected via the attach button", async () => {
    const user = userEvent.setup();
    uploadAttachmentMock.mockResolvedValue({ id: "srv-1", kind: "document", status: "ready", charCount: 11 });
    render(<Composer onSend={vi.fn()} onStop={vi.fn()} isSending={false} />);
    const file = new File(["hello world"], "notes.txt", { type: "text/plain" });
    // The hidden file inputs have no accessible label, so query by structure instead.
    const attachInput = document.querySelectorAll('input[type="file"]')[0] as HTMLInputElement;
    await user.upload(attachInput, file);
    expect(await screen.findByText("notes.txt")).toBeInTheDocument();
    expect(uploadAttachmentMock).toHaveBeenCalledTimes(1);
  });
  it("removes an attachment chip when its remove button is clicked", async () => {
    const user = userEvent.setup();
    uploadAttachmentMock.mockResolvedValue({ id: "srv-1", kind: "document", status: "ready" });
    render(<Composer onSend={vi.fn()} onStop={vi.fn()} isSending={false} />);
    const file = new File(["hello world"], "notes.txt", { type: "text/plain" });
    const attachInput = document.querySelectorAll('input[type="file"]')[0] as HTMLInputElement;
    await user.upload(attachInput, file);
    expect(await screen.findByText("notes.txt")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove notes.txt" }));
    await waitFor(() => expect(screen.queryByText("notes.txt")).not.toBeInTheDocument());
  });
  it("shows a failed state when the backend rejects an unsupported or invalid file", async () => {
    const user = userEvent.setup();
    uploadAttachmentMock.mockResolvedValue({
      id: "",
      kind: "document",
      status: "failed",
      error: "Unsupported attachment format 'exe'.",
    });
    render(<Composer onSend={vi.fn()} onStop={vi.fn()} isSending={false} />);
    const file = new File(["MZ"], "app.exe.txt", { type: "text/plain" });
    const attachInput = document.querySelectorAll('input[type="file"]')[0] as HTMLInputElement;
    await user.upload(attachInput, file);
    expect(await screen.findByText("Upload failed")).toBeInTheDocument();
  });
  it("rejects an unsupported extension client-side before uploading", async () => {
    const user = userEvent.setup();
    render(<Composer onSend={vi.fn()} onStop={vi.fn()} isSending={false} />);
    const file = new File(["binary"], "archive.zip", { type: "application/zip" });
    const attachInput = document.querySelectorAll('input[type="file"]')[0] as HTMLInputElement;
    await user.upload(attachInput, file);
    expect(await screen.findByText("Upload failed")).toBeInTheDocument();
    expect(uploadAttachmentMock).not.toHaveBeenCalled();
  });
  it("marks an image attachment with the image kind, not as a generic preview", async () => {
    const user = userEvent.setup();
    uploadAttachmentMock.mockResolvedValue({ id: "srv-2", kind: "image", status: "ready" });
    render(<Composer onSend={vi.fn()} onStop={vi.fn()} isSending={false} />);
    const file = new File(["binarydata"], "photo.png", { type: "image/png" });
    const imageInput = document.querySelectorAll('input[type="file"]')[1] as HTMLInputElement;
    await user.upload(imageInput, file);
    expect(await screen.findByText("photo.png")).toBeInTheDocument();
  });
  it("disables Send while an attachment is still uploading", async () => {
    const user = userEvent.setup();
    let resolveUpload: (value: { id: string; kind: string; status: string }) => void = () => {};
    uploadAttachmentMock.mockReturnValue(
      new Promise((resolve) => {
        resolveUpload = resolve;
      })
    );
    render(<Composer onSend={vi.fn()} onStop={vi.fn()} isSending={false} />);
    const file = new File(["hello world"], "notes.txt", { type: "text/plain" });
    const attachInput = document.querySelectorAll('input[type="file"]')[0] as HTMLInputElement;
    await user.upload(attachInput, file);
    await screen.findByText("notes.txt");
    const textarea = screen.getByLabelText("Message NEXA");
    await user.type(textarea, "Please look at this");
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    resolveUpload({ id: "srv-3", kind: "document", status: "ready" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Send message" })).not.toBeDisabled());
  });
  it("sends attachments along with the typed message once uploaded", async () => {
    const user = userEvent.setup();
    uploadAttachmentMock.mockResolvedValue({ id: "srv-4", kind: "document", status: "ready" });
    const onSend = vi.fn();
    render(<Composer onSend={onSend} onStop={vi.fn()} isSending={false} />);
    const file = new File(["hello world"], "notes.txt", { type: "text/plain" });
    const attachInput = document.querySelectorAll('input[type="file"]')[0] as HTMLInputElement;
    await user.upload(attachInput, file);
    await screen.findByText("notes.txt");
    await waitFor(() => expect(screen.getByRole("button", { name: "Send message" })).not.toBeDisabled());
    const textarea = screen.getByLabelText("Message NEXA");
    await user.type(textarea, "Please look at this{Enter}");
    expect(onSend).toHaveBeenCalledTimes(1);
    const [text, attachments] = onSend.mock.calls[0];
    expect(text).toBe("Please look at this");
    expect(attachments).toHaveLength(1);
    expect(attachments[0].name).toBe("notes.txt");
    expect(attachments[0].serverId).toBe("srv-4");
  });
});

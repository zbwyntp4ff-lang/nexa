import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KnowledgeSection } from "@/components/settings/sections/knowledge-section";
const {
  listKnowledgeDocumentsMock,
  addKnowledgeNoteMock,
  deleteKnowledgeDocumentMock,
  uploadKnowledgeDocumentMock,
} = vi.hoisted(() => ({
  listKnowledgeDocumentsMock: vi.fn(),
  addKnowledgeNoteMock: vi.fn(),
  deleteKnowledgeDocumentMock: vi.fn(),
  uploadKnowledgeDocumentMock: vi.fn(),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listKnowledgeDocuments: listKnowledgeDocumentsMock,
    addKnowledgeNote: addKnowledgeNoteMock,
    deleteKnowledgeDocument: deleteKnowledgeDocumentMock,
    uploadKnowledgeDocument: uploadKnowledgeDocumentMock,
  };
});
function makeDoc(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "doc-1",
    filename: "project-spec.pdf",
    source_type: "upload",
    source: "project-spec.pdf",
    format: "pdf",
    size_bytes: 12_345,
    status: "ready",
    error: null,
    chunk_count: 42,
    project_id: null,
    conversation_id: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}
describe("KnowledgeSection (Settings -> Knowledge Base)", () => {
  it("shows the empty state when there are no documents", async () => {
    listKnowledgeDocumentsMock.mockResolvedValue([]);
    render(<KnowledgeSection />);
    expect(await screen.findByText("No documents in the Knowledge Base yet.")).toBeInTheDocument();
  });
  it("shows Ready documents with their chunk count", async () => {
    listKnowledgeDocumentsMock.mockResolvedValue([makeDoc({ chunk_count: 42 })]);
    render(<KnowledgeSection />);
    expect(await screen.findByText("project-spec.pdf")).toBeInTheDocument();
    expect(screen.getByText(/Indexed/)).toBeInTheDocument();
    expect(screen.getByText(/42/)).toBeInTheDocument();
  });
  it("shows a Processing state", async () => {
    listKnowledgeDocumentsMock.mockResolvedValue([
      makeDoc({ id: "doc-2", filename: "research.pdf", status: "processing", chunk_count: 0 }),
    ]);
    render(<KnowledgeSection />);
    expect(await screen.findByText("research.pdf")).toBeInTheDocument();
    expect(screen.getByText(/Processing/)).toBeInTheDocument();
  });
  it("shows an Error state with the error message", async () => {
    listKnowledgeDocumentsMock.mockResolvedValue([
      makeDoc({ id: "doc-3", filename: "broken.pdf", status: "error", error: "Could not parse PDF." }),
    ]);
    render(<KnowledgeSection />);
    expect(await screen.findByText("broken.pdf")).toBeInTheDocument();
    expect(screen.getByText(/Could not parse PDF\./)).toBeInTheDocument();
  });
  it("adds a note and shows it in the list", async () => {
    const user = userEvent.setup();
    listKnowledgeDocumentsMock.mockResolvedValue([]);
    addKnowledgeNoteMock.mockResolvedValue(makeDoc({ id: "note-1", filename: "my-note", source_type: "note" }));
    render(<KnowledgeSection />);
    await screen.findByText("No documents in the Knowledge Base yet.");
    await user.type(screen.getByLabelText("Note title"), "my-note");
    await user.type(screen.getByLabelText("Note content..."), "Remember this fact.");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(addKnowledgeNoteMock).toHaveBeenCalledWith("my-note", "Remember this fact.");
    expect(await screen.findByText("my-note")).toBeInTheDocument();
  });
  it("removes a document when its remove button is clicked", async () => {
    const user = userEvent.setup();
    listKnowledgeDocumentsMock.mockResolvedValue([makeDoc()]);
    deleteKnowledgeDocumentMock.mockResolvedValue({ deleted: true, id: "doc-1" });
    render(<KnowledgeSection />);
    await screen.findByText("project-spec.pdf");
    await user.click(screen.getByRole("button", { name: /Remove document: project-spec.pdf/ }));
    await waitFor(() => expect(screen.queryByText("project-spec.pdf")).not.toBeInTheDocument());
    expect(deleteKnowledgeDocumentMock).toHaveBeenCalledWith("doc-1");
  });
});

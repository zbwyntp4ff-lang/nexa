import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorkflowPanel } from "@/components/workflows/workflow-panel";
import { useUiStore } from "@/store/ui-store";
const { listWorkflowsMock, createWorkflowMock, workflowActionMock } = vi.hoisted(() => ({
  listWorkflowsMock: vi.fn(),
  createWorkflowMock: vi.fn(),
  workflowActionMock: vi.fn(),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listWorkflows: listWorkflowsMock,
    createWorkflow: createWorkflowMock,
    workflowAction: workflowActionMock,
  };
});
const running = {
  id: "wf-1",
  name: "Research & Report",
  description: "Research topic X and prepare a short report with sources.",
  goal: "Research topic X",
  autonomy: "assisted",
  status: "RUNNING",
  progress: 0.75,
  current_task: "Review",
  error: null,
  final_result: null,
  sources: [],
  pending_approval: null,
  checkpoints: [{ name: "Research complete", completed_task_ids: ["a"] }],
  tasks: [
    { id: "a", name: "Research", description: "Research", status: "COMPLETED", agent: "research", error: null },
    { id: "b", name: "Analysis", description: "Analyze", status: "COMPLETED", agent: "planning", error: null },
    { id: "c", name: "Draft", description: "Draft", status: "COMPLETED", agent: "planning", error: null },
    { id: "d", name: "Review", description: "Review", status: "RUNNING", agent: "review", error: null },
  ],
};
describe("Workflows panel", () => {
  beforeEach(() => {
    listWorkflowsMock.mockReset();
    createWorkflowMock.mockReset();
    workflowActionMock.mockReset();
    useUiStore.setState({ workflowsOpen: true });
  });
  it("shows progress, tasks, status, and checkpoints", async () => {
    listWorkflowsMock.mockResolvedValue([running]);
    render(<WorkflowPanel />);
    expect(await screen.findAllByText("Research & Report")).not.toHaveLength(0);
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("Status: RUNNING")).toBeInTheDocument();
    expect(screen.getByText(/Research complete/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "75");
  });
  it("creates a workflow and shows an approval card", async () => {
    listWorkflowsMock.mockResolvedValue([]);
    createWorkflowMock.mockResolvedValue({
      ...running,
      id: "wf-2",
      name: "Files",
      status: "WAITING_APPROVAL",
      progress: 0,
      current_task: "Desktop",
      tasks: [{ id: "d", name: "Desktop", description: "Modify project files", status: "WAITING_APPROVAL", agent: "desktop", error: null }],
      checkpoints: [],
      pending_approval: {
        task_id: "d",
        agent: "Desktop Agent",
        action: "Modify project files",
        resources: ["a.md", "b.md", "c.md"],
        consequences: "May modify project files.",
      },
    });
    const user = userEvent.setup();
    render(<WorkflowPanel />);
    await screen.findByText(/no workflows yet/i);
    await user.type(screen.getByLabelText("Describe the task"), "Modify the project files");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByText("NEXA wants to perform an action")).toBeInTheDocument();
    expect(screen.getByText("Agent: Desktop Agent")).toBeInTheDocument();
    expect(screen.getByText("Files: 3")).toBeInTheDocument();
    workflowActionMock.mockResolvedValue({ ...running, id: "wf-2", status: "FAILED", error: "approval rejected", pending_approval: null, tasks: [] });
    await user.click(screen.getByRole("button", { name: "Reject" }));
    await waitFor(() => expect(workflowActionMock).toHaveBeenCalledWith("wf-2", "reject"));
  });
});

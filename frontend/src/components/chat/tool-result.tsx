"use client";
import { AlertTriangle, CheckCircle2, Wrench } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AgentStepView } from "@/lib/types";
function formatOutput(output: unknown): string {
  if (output === null || output === undefined) return "";
  if (typeof output === "string") return output;
  try {
    return JSON.stringify(output, null, 2);
  } catch {
    return String(output);
  }
}
/** Renders the tool-call steps NEXA's Agent took while producing a response. */
export function ToolResultList({ steps }: { steps: AgentStepView[] }) {
  const toolSteps = steps.filter((s) => s.stepType === "tool_call" || s.stepType === "error");
  if (toolSteps.length === 0) return null;
  return (
    <ol className="mb-3 space-y-2" aria-label="Tool calls">
      {toolSteps.map((step) => (
        <li
          key={step.index}
          className={cn(
            "rounded-lg border px-3 py-2 text-xs",
            step.success ? "border-border bg-muted/40" : "border-destructive/30 bg-destructive/5"
          )}
        >
          <div className="flex items-center gap-1.5 font-medium">
            {step.success ? (
              <CheckCircle2 className="size-3.5 text-success" aria-hidden="true" />
            ) : (
              <AlertTriangle className="size-3.5 text-destructive" aria-hidden="true" />
            )}
            <Wrench className="size-3.5 text-muted-foreground" aria-hidden="true" />
            <span>{step.toolName ?? "unknown tool"}</span>
            {step.dryRun && (
              <Badge variant="secondary" className="ml-1">
                dry-run
              </Badge>
            )}
          </div>
          {Object.keys(step.toolInput).length > 0 && (
            <pre className="mt-1 overflow-x-auto rounded bg-background/60 p-1.5 font-mono text-[11px] text-muted-foreground">
              {formatOutput(step.toolInput)}
            </pre>
          )}
          <p className="mt-1 text-muted-foreground">
            {step.success ? formatOutput(step.output) : (step.error ?? "This step failed.")}
          </p>
        </li>
      ))}
    </ol>
  );
}

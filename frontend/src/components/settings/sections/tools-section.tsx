import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n";
const TOOLS = [
  { name: "calculator", description: "Safe arithmetic evaluation (no eval, no code injection).", permission: "compute" },
  { name: "current_time", description: "Returns the current UTC time.", permission: "time" },
  { name: "file_read", description: "Reads a text file from the sandboxed agent workspace.", permission: "filesystem:read" },
  { name: "file_write", description: "Writes a text file to the sandboxed agent workspace.", permission: "filesystem:write" },
  { name: "directory_list", description: "Lists files in the sandboxed agent workspace.", permission: "filesystem:read" },
];
export function ToolsSection() {
  const t = useT();
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium">{t("tools.title")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("tools.desc")}</p>
      </div>
      <ul className="space-y-2">
        {TOOLS.map((tool) => (
          <li key={tool.name} className="rounded-lg border border-border p-3">
            <div className="flex items-center gap-2">
              <code className="text-sm font-medium">{tool.name}</code>
              <Badge variant="secondary">{tool.permission}</Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{tool.description}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

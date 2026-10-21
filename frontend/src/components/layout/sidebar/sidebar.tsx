"use client";
import { SidebarContent } from "./sidebar-content";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/store/ui-store";
/**
 * Desktop/laptop persistent sidebar. Collapses to zero width rather than a
 * drawer (drawers are reserved for mobile/tablet, see mobile-sidebar.tsx) -
 * the toggle button lives in the main header.
 */
export function DesktopSidebar() {
  const collapsed = useUiStore((s) => s.desktopSidebarCollapsed);
  return (
    <aside
      aria-label="Sidebar"
      aria-hidden={collapsed}
      className={cn(
        "hidden h-full min-h-0 shrink-0 overflow-hidden border-sidebar-border transition-[width,border-width] duration-200 lg:block",
        collapsed ? "w-0 border-r-0" : "w-72 border-r border-sidebar-border/60"
      )}
    >
      <div className="h-full min-h-0 w-72">
        <SidebarContent />
      </div>
    </aside>
  );
}

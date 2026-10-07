"use client";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { SidebarContent } from "./sidebar-content";
import { useUiStore } from "@/store/ui-store";
/** Sidebar -> Drawer on mobile/tablet, opened via the hamburger button in the header. */
export function MobileSidebar() {
  const open = useUiStore((s) => s.mobileDrawerOpen);
  const setOpen = useUiStore((s) => s.setMobileDrawerOpen);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent side="left" className="w-72 p-0">
        <SheetTitle className="sr-only">Sidebar</SheetTitle>
        <SidebarContent onNavigate={() => setOpen(false)} />
      </SheetContent>
    </Sheet>
  );
}

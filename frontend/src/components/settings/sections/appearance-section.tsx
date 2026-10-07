import { ThemeToggle } from "@/components/theme/theme-toggle";
import { useT } from "@/lib/i18n";
export function AppearanceSection() {
  const t = useT();
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium">{t("appearance.theme")}</h3>
        <p className="mt-1 mb-3 text-sm text-muted-foreground">{t("appearance.themeDesc")}</p>
        <ThemeToggle />
      </div>
    </div>
  );
}

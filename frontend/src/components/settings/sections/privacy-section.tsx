import { useT } from "@/lib/i18n";
export function PrivacySection() {
  const t = useT();
  return (
    <div className="space-y-4 text-sm text-muted-foreground">
      <h3 className="text-sm font-medium text-foreground">{t("privacy.title")}</h3>
      <ul className="list-disc space-y-2 pl-5">
        <li>{t("privacy.point1")}</li>
        <li>{t("privacy.point2")}</li>
        <li>{t("privacy.point3")}</li>
        <li>{t("privacy.point4")}</li>
        <li>{t("privacy.point5")}</li>
      </ul>
    </div>
  );
}

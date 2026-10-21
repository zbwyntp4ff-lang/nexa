"use client";
import * as React from "react";
import { fetchLegalDocument } from "@/lib/auth-api";
import { useT } from "@/lib/i18n";

const DOCS = ["terms_of_service", "privacy_policy", "license_agreement"] as const;

export function LegalDocButton({ doc }: { doc: (typeof DOCS)[number] }) {
  const t = useT();
  const [open, setOpen] = React.useState(false);
  const [body, setBody] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setError(null);
    void fetchLegalDocument(doc)
      .then((data) => {
        if (!cancelled) setBody(data.body);
      })
      .catch(() => {
        if (!cancelled) setError(t("auth.errorGeneric"));
      });
    return () => {
      cancelled = true;
    };
  }, [open, doc, t]);

  const label =
    doc === "terms_of_service"
      ? t("auth.acceptTerms")
      : doc === "privacy_policy"
        ? t("auth.acceptPrivacy")
        : t("auth.acceptLicense");

  return (
    <>
      <button
        type="button"
        className="text-left text-xs font-medium text-primary underline-offset-4 hover:underline"
        onClick={() => setOpen(true)}
      >
        {label}
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog">
          <div className="max-h-[80dvh] w-full max-w-lg overflow-y-auto rounded-xl border border-border bg-background p-5 shadow-xl">
            <p className="mb-3 text-sm font-semibold">{label}</p>
            {error && <p className="text-sm text-destructive">{error}</p>}
            {!error && !body && <p className="text-sm text-muted-foreground">…</p>}
            {body && <pre className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{body}</pre>}
            <button
              type="button"
              className="mt-4 text-sm font-medium text-primary"
              onClick={() => setOpen(false)}
            >
              OK
            </button>
          </div>
        </div>
      )}
    </>
  );
}

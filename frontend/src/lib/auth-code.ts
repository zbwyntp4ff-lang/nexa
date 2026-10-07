/** Normalize a pasted/typed email verification code to up to 6 digits. */
export function normalizeVerificationCode(raw: string): string {
  return raw.replace(/\D/g, "").slice(0, 6);
}

/** Apply clipboard text into a code field (works even when paste exceeds maxLength). */
export function codeFromPasteEvent(e: { clipboardData: DataTransfer | null }): string {
  const text = e.clipboardData?.getData("text") ?? "";
  return normalizeVerificationCode(text);
}

/** Strip clipboard / mailto artifacts from an email field value. */
export function normalizeEmailInput(value: string): string {
  let email = (value || "").replace(/[\r\n\u200b-\u200d\uFEFF\u00AD]/g, "").trim();
  email = email.replace(/^mailto:/i, "").trim();
  email = email.replace(/^[\s'"<>]+|[\s'"<>]+$/g, "");
  // Remove remaining Unicode spaces without touching valid local-part chars.
  email = email.replace(/\s+/g, "");
  // Leading bullets / rich-text junk from paste or corrupt storage.
  email = email.replace(/^[^A-Za-z0-9._%+-]+/, "");
  return email;
}

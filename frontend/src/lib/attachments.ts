import { API_BASE_URL } from "./api";
import { authHeaders, getSessionToken } from "./session-token";
import type { AttachmentKind, AttachmentUploadOutcome, AttachmentView } from "./types";
const IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "webp", "gif"]);
const DOCUMENT_EXTENSIONS = new Set(["txt", "md", "csv", "json", "pdf", "docx", "xlsx"]);
const ALLOWED_EXTENSIONS = new Set<string>([...IMAGE_EXTENSIONS, ...DOCUMENT_EXTENSIONS]);
/** Mirrors the backend defaults (see .env.example) so the UI can reject an
 * obviously-too-large or unsupported file before spending a round trip -
 * the server re-validates everything regardless (signature check, real
 * size limit), this is only a fast client-side hint. */
export const DEFAULT_MAX_ATTACHMENT_SIZE_BYTES = 10_000_000;
export const DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE = 5;
function extensionOf(filename: string): string {
  const idx = filename.lastIndexOf(".");
  return idx === -1 ? "" : filename.slice(idx + 1).toLowerCase();
}
function kindFor(extension: string): AttachmentKind {
  return IMAGE_EXTENSIONS.has(extension) ? "image" : "document";
}
function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `file-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
/** Fast client-side pre-check. The backend is the real authority (signature
 * + size + whitelist validation happens there regardless). */
export function validateLocalFile(file: File, maxSizeBytes: number = DEFAULT_MAX_ATTACHMENT_SIZE_BYTES): string | null {
  if (file.size === 0) return "This file is empty.";
  const extension = extensionOf(file.name);
  if (!ALLOWED_EXTENSIONS.has(extension)) {
    return `Unsupported file type "${extension ? `.${extension}` : "unknown"}".`;
  }
  if (file.size > maxSizeBytes) {
    return `This file is too large (max ${formatFileSize(maxSizeBytes)}).`;
  }
  return null;
}
function tryCreateObjectUrl(file: File): string | undefined {
  try {
    return typeof URL !== "undefined" && "createObjectURL" in URL ? URL.createObjectURL(file) : undefined;
  } catch {
    return undefined;
  }
}
/** Build the initial, client-only view for a newly-selected file (before/while uploading). */
export function createLocalAttachment(file: File): AttachmentView {
  const extension = extensionOf(file.name);
  const kind = kindFor(extension);
  return {
    id: makeId(),
    name: file.name,
    size: file.size,
    mimeType: file.type || "application/octet-stream",
    kind,
    status: "uploading",
    progress: 0,
    previewUrl: kind === "image" ? tryCreateObjectUrl(file) : undefined,
  };
}
/**
 * Uploads one real file to `POST /api/v1/attachments` with byte-level
 * progress (via XHR, since `fetch` has no reliable upload progress event).
 * Resolves (never rejects) with the outcome so callers can show a clear,
 * per-file error instead of a thrown exception.
 */
export function uploadAttachment(file: File, onProgress?: (percent: number) => void): Promise<AttachmentUploadOutcome> {
  const extension = extensionOf(file.name);
  const fallbackKind = kindFor(extension);
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let body: Record<string, unknown> = {};
      try {
        body = JSON.parse(xhr.responseText || "{}");
      } catch {
        // fall through with an empty body - handled as a generic failure below
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        const status = body.status === "failed" ? "failed" : "ready";
        resolve({
          id: String(body.id ?? ""),
          kind: (body.kind as AttachmentKind) ?? fallbackKind,
          status,
          error: status === "failed" ? String(body.error ?? "Processing failed.") : undefined,
          charCount: typeof body.char_count === "number" ? body.char_count : undefined,
          pageCount: typeof body.page_count === "number" ? body.page_count : undefined,
        });
      } else {
        resolve({
          id: "",
          kind: fallbackKind,
          status: "failed",
          error: String(body.message ?? `Upload failed (${xhr.status}).`),
        });
      }
    };
    xhr.onerror = () => {
      resolve({ id: "", kind: fallbackKind, status: "failed", error: "Could not reach the NEXA backend." });
    };
    xhr.open("POST", `${API_BASE_URL}/api/v1/attachments`);
    xhr.withCredentials = true;
    const token = getSessionToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.send(formData);
  });
}
export function safeRevokeObjectUrl(url: string | undefined): void {
  if (!url) return;
  try {
    if (typeof URL !== "undefined" && "revokeObjectURL" in URL) URL.revokeObjectURL(url);
  } catch {
    // best-effort cleanup only
  }
}
export function deleteAttachmentBestEffort(serverId: string): void {
  fetch(`${API_BASE_URL}/api/v1/attachments/${serverId}`, {
    method: "DELETE",
    credentials: "include",
    headers: authHeaders(),
  }).catch(() => {
    // best-effort - the server also expires attachments on its own via TTL
  });
}

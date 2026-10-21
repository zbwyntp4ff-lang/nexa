/** Part 11 — profile / personalization API (cookie session). */
import { request } from "./api";

export type ResponseStyle = "concise" | "balanced" | "detailed" | "technical";
export type Personality = "professional" | "friendly" | "direct" | "technical";
export type DetailLevel = "low" | "medium" | "high";
export type AnswerFormat = "auto" | "prose" | "bullets" | "structured";

export interface AIPreferences {
  personalization_enabled: boolean;
  response_style: ResponseStyle;
  personality: Personality;
  brevity: DetailLevel;
  detail_level: DetailLevel;
  answer_format: AnswerFormat;
  ai_language: string;
  default_model: string | null;
  preferred_name: string;
}

export interface UserProfile {
  user_id: string;
  display_name: string;
  avatar_data_url: string | null;
  ui_language: string;
  theme: string;
  ai: AIPreferences;
  onboarding_completed: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectPersonalizationPayload {
  preferred_model?: string | null;
  response_style?: ResponseStyle | null;
  ai_language?: string | null;
  instructions?: string | null;
  use_personal_context?: boolean | null;
}

export function fetchProfile(signal?: AbortSignal) {
  return request<{ profile: UserProfile }>("/api/v1/profile", { signal });
}

export function updateProfile(
  patch: Partial<{
    display_name: string;
    avatar_data_url: string | null;
    ui_language: string;
    theme: string;
    ai: AIPreferences;
    onboarding_completed: boolean;
  }>,
  signal?: AbortSignal,
) {
  return request<{ profile: UserProfile }>("/api/v1/profile", {
    method: "PATCH",
    body: JSON.stringify(patch),
    signal,
  });
}

export function fetchContextPreview(signal?: AbortSignal) {
  return request<{ enabled: boolean; hint: string | null; max_chars: number }>(
    "/api/v1/profile/context-preview",
    { signal },
  );
}

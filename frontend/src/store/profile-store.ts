"use client";
import { create } from "zustand";
import {
  fetchProfile,
  updateProfile,
  type AIPreferences,
  type UserProfile,
} from "@/lib/profile-api";

interface ProfileState {
  profile: UserProfile | null;
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
  save: (patch: Parameters<typeof updateProfile>[0]) => Promise<UserProfile>;
  patchAi: (partial: Partial<AIPreferences>) => Promise<UserProfile>;
}

export const useProfileStore = create<ProfileState>((set, get) => ({
  profile: null,
  loading: false,
  error: null,

  load: async () => {
    set({ loading: true, error: null });
    try {
      const { profile } = await fetchProfile();
      set({ profile, loading: false });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : "Failed to load profile",
        profile: null,
      });
    }
  },

  save: async (patch) => {
    const { profile } = await updateProfile(patch);
    set({ profile, error: null });
    return profile;
  },

  patchAi: async (partial) => {
    const current = get().profile;
    const base: AIPreferences = current?.ai ?? {
      personalization_enabled: true,
      response_style: "balanced",
      personality: "friendly",
      brevity: "medium",
      detail_level: "medium",
      answer_format: "auto",
      ai_language: "",
      default_model: null,
      preferred_name: "",
      custom_instructions: "",
      about_user: "",
      occupation: "",
      interests: [],
      avoid_topics: "",
      expertise_level: "intermediate",
      proactive_suggestions: true,
    };
    return get().save({ ai: { ...base, ...partial } });
  },
}));

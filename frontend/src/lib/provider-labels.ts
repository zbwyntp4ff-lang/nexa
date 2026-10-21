/** Human labels for model gateway providers (never shows API keys). */
export function providerLabel(provider: string): string {
  switch (provider) {
    case "openai":
      return "OpenAI";
    case "anthropic":
      return "Anthropic";
    case "gemini":
      return "Google Gemini";
    case "openrouter":
      return "OpenRouter";
    case "ollama":
    case "local":
      return "Ollama";
    case "mock":
      return "Mock";
    case "auto":
      return "Auto";
    default:
      return provider;
  }
}

/** Providers selectable in Settings / quick switch (besides auto). */
export const SELECTABLE_PROVIDERS = [
  "auto",
  "openai",
  "anthropic",
  "gemini",
  "openrouter",
  "ollama",
] as const;

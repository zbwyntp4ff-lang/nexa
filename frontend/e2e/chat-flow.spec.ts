import { test, expect } from "@playwright/test";

function streamReply(message: string) {
  const delta = JSON.stringify({ type: "delta", text: message });
  const done = JSON.stringify({ type: "done", provider: "mock", model: "nexa-mock-1", ttft_ms: 1, total_ms: 2 });
  return `data: ${delta}\n\ndata: ${done}\n\n`;
}

const testUser = {
  id: "e2e-user",
  first_name: "Test",
  last_name: "User",
  username: "e2e",
  email: "e2e@example.test",
  email_verified: true,
  is_active: true,
  consents: [],
  created_at: "2026-01-01T00:00:00Z",
};

const testProfile = {
  user_id: "e2e-user",
  display_name: "Test User",
  avatar_data_url: null,
  ui_language: "en",
  theme: "system",
  ai: {
    personalization_enabled: true,
    response_style: "balanced",
    personality: "friendly",
    brevity: "medium",
    detail_level: "medium",
    answer_format: "auto",
    ai_language: "en",
    default_model: null,
    preferred_name: "",
    custom_instructions: "",
    about_user: "",
    occupation: "",
    interests: [],
    avoid_topics: "",
    expertise_level: "intermediate",
    proactive_suggestions: true,
  },
  onboarding_completed: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

test.beforeEach(async ({ page }) => {
  // The E2E suite uses a deterministic authenticated test session. No real
  // backend, account, provider credential, or external API is contacted.
  await page.route("**/health", async (route) => {
    await route.fulfill({ json: { status: "ok" } });
  });
  await page.route("**/api/v1/auth/status", async (route) => {
    await route.fulfill({
      json: {
        single_user: false,
        has_user: true,
        registration_open: true,
        skip_email_verification: true,
      },
    });
  });
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({ json: { user: testUser } });
  });
  await page.route("**/api/v1/profile", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: { profile: testProfile } });
      return;
    }
    await route.fulfill({ json: { profile: testProfile } });
  });
  await page.route("**/api/v1/conversations**", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: [] });
      return;
    }
    const body = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        ...body,
        id: body.id ?? "e2e-conversation",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: new Date().toISOString(),
      },
    });
  });
  await page.route("**/api/v1/chat/stream", async (route) => {
    const body = route.request().postDataJSON() as { message: string };
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream; charset=utf-8", "cache-control": "no-cache" },
      body: streamReply(`[mock:nexa-mock-1] You said: ${body.message}`),
    });
  });
});

test("Open NEXA -> New Chat -> type message -> Send -> receive response", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("NEXA AI")).toBeVisible();
  await expect(page.getByText("Think. Create. Act.")).toBeVisible();
  await page.getByRole("button", { name: "New chat" }).click();
  const composer = page.getByLabel("Message NEXA");
  await composer.click();
  await composer.fill("Hello, NEXA!");
  await composer.press("Enter");
  const conversation = page.getByLabel("Conversation");
  await expect(conversation.getByText("Hello, NEXA!", { exact: true })).toBeVisible();
  await expect(conversation.getByText("[mock:nexa-mock-1] You said: Hello, NEXA!")).toBeVisible({
    timeout: 10_000,
  });
  await expect(page.getByRole("button", { name: "Hello, NEXA!", exact: true })).toBeVisible();
});

test("shows the Thinking status while waiting for a response", async ({ page }) => {
  await page.route("**/api/v1/chat/stream", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream; charset=utf-8" },
      body: streamReply("Delayed response"),
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "New chat" }).click();
  const composer = page.getByLabel("Message NEXA");
  await composer.fill("Are you there?");
  await composer.press("Enter");
  await expect(page.getByText("Thinking…")).toBeVisible();
  await expect(page.getByText("Delayed response")).toBeVisible({ timeout: 10_000 });
});

test("shows an error message when the backend call fails", async ({ page }) => {
  await page.route("**/api/v1/chat/stream", async (route) => {
    await route.fulfill({
      status: 503,
      json: { error: "ProviderConfigurationError", message: "Provider is not configured correctly." },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "New chat" }).click();
  const composer = page.getByLabel("Message NEXA");
  await composer.fill("This will fail");
  await composer.press("Enter");
  await expect(page.getByText("Provider is not configured correctly.")).toBeVisible({ timeout: 10_000 });
});

test("switches to dark mode from Settings and it persists across reload", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByRole("button", { name: "Appearance" }).click();
  await page.getByRole("radio", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
});

test("mobile viewport shows a hamburger menu that opens the sidebar as a drawer", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Open sidebar" })).toBeVisible();
  await page.getByRole("button", { name: "Open sidebar" }).click();
  await expect(page.getByRole("button", { name: "New chat" })).toBeVisible();
});

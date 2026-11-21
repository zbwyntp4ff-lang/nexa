import { test, expect } from "@playwright/test";

const user = {
  id: "ipad-e2e-user",
  first_name: "iPad",
  last_name: "Test",
  username: "ipad-test",
  email: "ipad@example.test",
  email_verified: true,
  is_active: true,
  consents: [],
  created_at: "2026-01-01T00:00:00Z",
};

const profile = {
  user_id: "ipad-e2e-user",
  display_name: "iPad Test",
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

test("iPad Safari renders authenticated NEXA and keeps the composer usable", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 1366 });
  await page.route("**/health", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("**/api/v1/auth/status", (route) =>
    route.fulfill({
      json: {
        single_user: false,
        has_user: true,
        registration_open: true,
        skip_email_verification: true,
      },
    }),
  );
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: { user } }));
  await page.route("**/api/v1/profile", (route) =>
    route.fulfill({ json: { profile } }),
  );
  await page.route("**/api/v1/conversations**", (route) =>
    route.fulfill({ json: [] }),
  );

  await page.goto("/");
  await expect(page.getByText("NEXA AI")).toBeVisible();
  const composer = page.getByLabel("Message NEXA");
  await expect(composer).toBeVisible();
  await expect(page.getByRole("button", { name: "New chat" })).toBeVisible();
  await composer.fill("Safari iPad layout check");
  await expect(composer).toHaveValue("Safari iPad layout check");
});

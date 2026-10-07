import { test, expect } from "@playwright/test";
/**
 * The required Part 4 E2E flow: Open NEXA -> New Chat -> type message ->
 * Send -> receive response.
 *
 * The backend is mocked via route interception so this test is hermetic and
 * never depends on (or calls) a real external service - consistent with the
 * "no external calls in tests" principle used throughout this project.
 */
test.beforeEach(async ({ page }) => {
  await page.route("**/health", async (route) => {
    await route.fulfill({ json: { status: "ok" } });
  });
  await page.route("**/api/v1/chat", async (route) => {
    const body = route.request().postDataJSON() as { message: string };
    await route.fulfill({
      json: {
        message: `[mock:nexa-mock-1] You said: ${body.message}`,
        provider: "mock",
        model: "nexa-mock-1",
        latency_ms: 1.23,
        created_at: new Date().toISOString(),
      },
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
  // The new conversation should now be listed in the sidebar's recent chats.
  await expect(page.getByRole("button", { name: "Hello, NEXA!", exact: true })).toBeVisible();
});
test("shows the Thinking status while waiting for a response", async ({ page }) => {
  await page.route("**/api/v1/chat", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.fulfill({
      json: {
        message: "Delayed response",
        provider: "mock",
        model: "nexa-mock-1",
        latency_ms: 500,
        created_at: new Date().toISOString(),
      },
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
  await page.route("**/api/v1/chat", async (route) => {
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

import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { ThemeToggle } from "@/components/theme/theme-toggle";
function renderWithTheme() {
  return render(
    <ThemeProvider>
      <ThemeToggle />
    </ThemeProvider>
  );
}
describe("ThemeToggle", () => {
  it("renders Light, Dark, and System options", () => {
    renderWithTheme();
    expect(screen.getByRole("radio", { name: "Light" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Dark" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "System" })).toBeInTheDocument();
  });
  it("switches to dark mode and applies the .dark class to <html>", async () => {
    const user = userEvent.setup();
    renderWithTheme();
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    await waitFor(() => expect(document.documentElement).toHaveClass("dark"));
    expect(screen.getByRole("radio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
  });
  it("switches back to light mode and removes the .dark class", async () => {
    const user = userEvent.setup();
    renderWithTheme();
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    await waitFor(() => expect(document.documentElement).toHaveClass("dark"));
    await user.click(screen.getByRole("radio", { name: "Light" }));
    await waitFor(() => expect(document.documentElement).not.toHaveClass("dark"));
    expect(screen.getByRole("radio", { name: "Light" })).toHaveAttribute("aria-checked", "true");
  });
  it("persists the chosen theme to localStorage under the nexa-theme key", async () => {
    const user = userEvent.setup();
    renderWithTheme();
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    await waitFor(() => expect(localStorage.getItem("nexa-theme")).toBe("dark"));
  });
});

import { describe, expect, it } from "vitest";
import { initialAuthScreen } from "@/lib/auth-api";

describe("initialAuthScreen", () => {
  it("shows owner setup only when registration is open and there is no user yet", () => {
    expect(
      initialAuthScreen({
        single_user: true,
        has_user: false,
        registration_open: true,
        skip_email_verification: true,
      }),
    ).toBe("ownerSetup");
  });

  it("shows login when an account already exists", () => {
    expect(
      initialAuthScreen({
        single_user: false,
        has_user: true,
        registration_open: true,
        skip_email_verification: true,
      }),
    ).toBe("login");
  });

  it("shows login when status is unknown", () => {
    expect(initialAuthScreen(null)).toBe("login");
  });
});

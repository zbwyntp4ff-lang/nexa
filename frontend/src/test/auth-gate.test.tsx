import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGate } from "@/components/auth/auth-gate";
import { LoginForm } from "@/components/auth/login-form";
import { OwnerSetupForm } from "@/components/auth/owner-setup-form";
import { useAuthStore } from "@/store/auth-store";

vi.mock("@/lib/auth-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth-api")>();
  return {
    ...actual,
    fetchAuthProviders: vi.fn(async () => ({
      oauth: [],
      device: { id: "device", label: "QR", enabled: true, kind: "device" },
      passkey: { id: "passkey", label: "Passkey", enabled: true, kind: "passkey" },
      password: { id: "password", label: "Email", enabled: true, kind: "password" },
    })),
    fetchAuthStatus: vi.fn(async () => ({
      single_user: false,
      has_user: true,
      registration_open: true,
      skip_email_verification: true,
    })),
    fetchMe: vi.fn(async () => {
      throw new Error("anonymous");
    }),
  };
});

function resetAuth(overrides: Partial<ReturnType<typeof useAuthStore.getState>> = {}) {
  useAuthStore.setState({
    status: "anonymous",
    user: null,
    authStatus: {
      single_user: false,
      has_user: false,
      registration_open: true,
      skip_email_verification: true,
    },
    screen: "login",
    pendingEmail: "",
    codeExpiresAt: null,
    resendAvailableAt: null,
    bootstrap: async () => undefined,
    ...overrides,
  });
}

describe("auth sign-in affordance", () => {
  beforeEach(() => {
    resetAuth();
  });

  it("shows a Sign in button on the login form", () => {
    render(<LoginForm />);
    expect(screen.getByTestId("auth-sign-in")).toHaveTextContent(/sign in/i);
  });

  it("shows a Sign in button on owner setup", async () => {
    const user = userEvent.setup();
    render(<OwnerSetupForm />);
    const signIn = screen.getByTestId("auth-sign-in");
    expect(signIn).toHaveTextContent(/sign in/i);
    await user.click(signIn);
    expect(useAuthStore.getState().screen).toBe("login");
  });

  it("shows create-account on login when registration is open and users already exist", () => {
    resetAuth({
      screen: "login",
      authStatus: {
        single_user: false,
        has_user: true,
        registration_open: true,
        skip_email_verification: true,
      },
    });
    render(<LoginForm />);
    expect(screen.getByTestId("auth-sign-in")).toBeInTheDocument();
    expect(screen.getByTestId("auth-create-account")).toBeInTheDocument();
  });

  it("allows registration screen when multi-user registration is open", () => {
    resetAuth({
      screen: "ownerSetup",
      authStatus: {
        single_user: false,
        has_user: true,
        registration_open: true,
        skip_email_verification: true,
      },
    });
    render(
      <AuthGate>
        <div>app</div>
      </AuthGate>,
    );
    expect(screen.getByRole("heading", { name: /create account/i })).toBeInTheDocument();
  });
});


import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TokensSection } from "@/components/settings/sections/tokens-section";
import * as tokensApi from "@/lib/tokens-api";
import { useTokensStore } from "@/store/tokens-store";

vi.mock("@/lib/tokens-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/tokens-api")>();
  return {
    ...actual,
    fetchTokenBalance: vi.fn(),
    fetchTokenHistory: vi.fn(),
  };
});

const balance = {
  user_id: "u1",
  balance: 40,
  daily_limit: 100,
  monthly_limit: 1000,
  daily_spent: 10,
  monthly_spent: 20,
  daily_period: "2026-10-17",
  monthly_period: "2026-10",
  updated_at: new Date().toISOString(),
  unit: "nexa_credits",
  costs: { chat: 1, agent: 5, image: 10, default: 1 },
  usage_by_reason: [{ reason: "chat", spent: 10, count: 10 }],
};

describe("TokensSection flicker regression", () => {
  beforeEach(() => {
    useTokensStore.getState().reset();
    useTokensStore.setState({ generation: 0, phase: "idle" });
    vi.mocked(tokensApi.fetchTokenBalance).mockResolvedValue(balance);
    vi.mocked(tokensApi.fetchTokenHistory).mockResolvedValue({
      items: [],
      limit: 40,
      offset: 0,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    useTokensStore.getState().reset();
  });

  it("loads once on mount and keeps panel mounted on soft refresh", async () => {
    const user = userEvent.setup();
    render(<TokensSection />);

    await waitFor(() => {
      expect(screen.getByTestId("tokens-panel")).toBeInTheDocument();
    });
    expect(tokensApi.fetchTokenBalance).toHaveBeenCalledTimes(1);

    await user.click(screen.getByTestId("tokens-refresh"));
    await waitFor(() => {
      expect(tokensApi.fetchTokenBalance).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByTestId("tokens-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("tokens-loading")).not.toBeInTheDocument();
  });

  it("does not show full-page loading when cache exists after remount", async () => {
    const { unmount } = render(<TokensSection />);
    await waitFor(() => expect(screen.getByTestId("tokens-panel")).toBeInTheDocument());
    unmount();

    // Slow second fetch must not flash the loading spinner — cache is shown.
    let resolveBalance!: (v: typeof balance) => void;
    vi.mocked(tokensApi.fetchTokenBalance).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveBalance = resolve;
        }),
    );

    render(<TokensSection />);
    expect(screen.getByTestId("tokens-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("tokens-loading")).not.toBeInTheDocument();

    await act(async () => {
      resolveBalance(balance);
    });
    await waitFor(() => {
      expect(screen.getByTestId("tokens-panel")).toBeInTheDocument();
    });
  });

  it("shows usage-by-reason and cost schedule from server", async () => {
    render(<TokensSection />);
    await waitFor(() => expect(screen.getByTestId("tokens-panel")).toBeInTheDocument());
    expect(screen.getByTestId("tokens-usage-by-reason")).toBeInTheDocument();
    expect(screen.getByTestId("tokens-costs")).toBeInTheDocument();
  });
});

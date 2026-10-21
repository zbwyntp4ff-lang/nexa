import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { useT } from "@/lib/i18n";
import { useI18nStore } from "@/lib/i18n-store";

describe("useT stability", () => {
  it("keeps the same function identity across re-renders when language is unchanged", () => {
    useI18nStore.setState({ language: "en" });
    const { result, rerender } = renderHook(() => useT());
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
    expect(first("tokens.title")).toMatch(/token|limit/i);
  });
});

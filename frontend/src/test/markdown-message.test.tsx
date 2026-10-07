import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarkdownMessage } from "@/components/chat/markdown-message";
describe("MarkdownMessage", () => {
  it("renders a fenced code block as <pre><code> with highlight.js classes applied", () => {
    const content = ["```python", "def foo():", "    return 42", "```"].join("\n");
    render(<MarkdownMessage content={content} />);
    const codeElement = document.querySelector("pre code");
    expect(codeElement).toBeInTheDocument();
    expect(codeElement).toHaveClass("hljs");
    expect(codeElement?.textContent).toContain("def foo():");
    // rehype-highlight tokenizes keywords into spans - "def" is a keyword in Python.
    expect(codeElement?.querySelector(".hljs-keyword, .hljs-title, .hljs-title.function_")).toBeTruthy();
  });
  it("renders GFM tables", () => {
    const content = ["| A | B |", "| - | - |", "| 1 | 2 |"].join("\n");
    render(<MarkdownMessage content={content} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
  });
  it("renders GFM lists", () => {
    render(<MarkdownMessage content={"- one\n- two\n- three"} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });
  it("renders links with target=_blank and rel=noopener", () => {
    render(<MarkdownMessage content="[NEXA](https://example.com)" />);
    const link = screen.getByRole("link", { name: "NEXA" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
  it("renders images", () => {
    render(<MarkdownMessage content="![alt text](https://example.com/pic.png)" />);
    const img = screen.getByRole("img", { name: "alt text" });
    expect(img).toHaveAttribute("src", "https://example.com/pic.png");
  });
  it("preserves multi-line code content (newlines are not collapsed)", () => {
    const content = ["```", "line one", "line two", "line three", "```"].join("\n");
    render(<MarkdownMessage content={content} />);
    const codeElement = document.querySelector("pre code");
    expect(codeElement?.textContent).toBe("line one\nline two\nline three\n");
  });
});

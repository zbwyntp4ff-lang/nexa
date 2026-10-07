"use client";
import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
function CodeBlockCopyButton({ getText }: { getText: () => string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(getText());
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          // Clipboard API unavailable - fail silently, nothing to recover from.
        }
      }}
      aria-label="Copy code"
      className="absolute top-2 right-2 rounded-md border border-border bg-background/80 p-1 text-muted-foreground opacity-0 backdrop-blur transition-opacity group-hover:opacity-100 hover:text-foreground focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {copied ? <Check className="size-3.5" aria-hidden="true" /> : <Copy className="size-3.5" aria-hidden="true" />}
    </button>
  );
}
/** Renders Markdown (GFM tables/lists/links/images) with highlighted code blocks. */
export function MarkdownMessage({ content, className }: { content: string; className?: string }) {
  const preRef = React.useRef<HTMLPreElement | null>(null);
  return (
    <div className={cn("nexa-markdown text-sm", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          pre({ children, ...props }) {
            return (
              <div className="group relative">
                <pre {...props} ref={preRef}>
                  {children}
                </pre>
                <CodeBlockCopyButton getText={() => preRef.current?.textContent ?? ""} />
              </div>
            );
          },
          a({ href, children, ...props }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                {children}
              </a>
            );
          },
          img({ alt, ...props }) {
            // eslint-disable-next-line @next/next/no-img-element
            return <img alt={alt ?? ""} loading="lazy" {...props} />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

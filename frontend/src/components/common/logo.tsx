import Image from "next/image";
import { cn } from "@/lib/utils";
/**
 * NEXA's brand logo — uses the user-provided nexa-logo.png.
 * Falls back to the SVG gradient mark if the image hasn't loaded.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <Image
      src="/nexa-logo.png"
      alt="NEXA"
      width={32}
      height={32}
      className={cn("size-6 rounded-full object-cover", className)}
      priority
    />
  );
}
export function LogoWordmark({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2 font-semibold tracking-tight", className)}>
      <span className="flex size-8 items-center justify-center rounded-lg nexa-gradient-chat text-sm font-bold text-white shadow-md">
        N
      </span>
      <span className="nexa-gradient-text text-lg">NEXA</span>
    </span>
  );
}

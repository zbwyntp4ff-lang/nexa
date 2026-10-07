import { cn } from "@/lib/utils";

/** Glowing circular N mark used on the empty chat hero. */
export function NexaOrb({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "nexa-orb nexa-pop-in relative flex size-28 items-center justify-center rounded-full",
        className
      )}
      aria-hidden="true"
    >
      <span className="text-5xl font-semibold tracking-tight text-white drop-shadow-[0_0_18px_rgba(180,160,255,0.85)]">
        N
      </span>
    </div>
  );
}

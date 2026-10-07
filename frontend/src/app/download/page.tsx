"use client";
import Link from "next/link";
import { Download, Globe } from "lucide-react";
import { LogoWordmark } from "@/components/common/logo";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") || "";
const DOWNLOAD_URL =
  process.env.NEXT_PUBLIC_DOWNLOAD_URL?.trim() || "/downloads/NEXA-Setup.exe";
const APP_URL = SITE_URL ? `${SITE_URL}/` : "/";

/** Public page: open in Chrome + download Windows installer. */
export default function DownloadPage() {
  return (
    <div className="nexa-chat-atmosphere relative min-h-dvh overflow-hidden text-foreground">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(120,90,255,0.18),transparent_55%),radial-gradient(ellipse_at_bottom_right,rgba(80,180,255,0.12),transparent_50%)]"
      />
      <main className="relative mx-auto flex min-h-dvh w-full max-w-3xl flex-col justify-center px-6 py-16">
        <LogoWordmark className="mb-8 text-2xl" />
        <h1 className="max-w-xl text-4xl font-semibold tracking-tight sm:text-5xl">NEXA</h1>
        <p className="mt-3 max-w-lg text-lg text-muted-foreground">
          Think. Create. Act. Open NEXA in Chrome or download the Windows app.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <a href={APP_URL} className={cn(buttonVariants({ size: "lg" }), "h-11 px-5")}>
            <Globe className="size-4" aria-hidden="true" />
            Open in browser
          </a>
          <a
            href={DOWNLOAD_URL}
            download
            className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-11 px-5")}
          >
            <Download className="size-4" aria-hidden="true" />
            Download for Windows
          </a>
        </div>
        <p className="mt-6 text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/" className="font-medium text-primary underline-offset-4 hover:underline">
            Sign in
          </Link>
        </p>
      </main>
    </div>
  );
}

import type { ReactNode } from "react";

import { SiteFooter } from "@/components/brand";
import { Header } from "@/components/Header";

/** Date the information pages were last reviewed, shown at their foot. */
export const INFO_UPDATED = "16 October 2026";

/** The shared frame of the information pages: header, heading, text, footer. */
export function InfoPage({
  kicker,
  title,
  intro,
  children,
}: {
  kicker: string;
  title: string;
  intro: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col">
      <Header />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12 md:px-12">
        <p className="kicker text-accent-strong">{kicker}</p>
        <h1 className="mt-2 text-4xl tracking-tight md:text-5xl">{title}</h1>
        <p className="text-ink-2 mt-4 text-lg leading-relaxed">{intro}</p>
        <div className="prose-info mt-4">{children}</div>
        <p className="text-muted mt-14 text-sm">Last updated {INFO_UPDATED}</p>
      </main>
      <SiteFooter compact />
    </div>
  );
}

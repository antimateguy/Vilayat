// The Vilayat brand pieces: the six-colour flag stripe, the logo and the
// footer. The stripe joins the German (black, red, gold) and Indian (saffron,
// white, green) flags; it is decoration and is hidden from screen readers.

import Link from "next/link";

import { INFO_PAGES } from "@/lib/info-pages";

const STRIPE = [
  "bg-de-black",
  "bg-de-red",
  "bg-de-gold",
  "bg-in-saffron",
  "bg-white",
  "bg-in-green",
];

export function FlagStripe({ height = "h-1.5" }: { height?: string }) {
  return (
    <div aria-hidden className={`flex ${height}`}>
      {STRIPE.map((colour) => (
        <span key={colour} className={`flex-1 ${colour}`} />
      ))}
    </div>
  );
}

/** Two little flags side by side: Germany and India. */
export function LogoMark({ size = "md" }: { size?: "sm" | "md" }) {
  const column = size === "md" ? "w-[13px]" : "w-[10px]";
  const cell = size === "md" ? "h-[7px]" : "h-[5px]";
  return (
    <span aria-hidden className="grid grid-cols-2 gap-[3px]">
      <span className={`flex flex-col ${column}`}>
        <span className={`${cell} bg-de-black`} />
        <span className={`${cell} bg-de-red`} />
        <span className={`${cell} bg-de-gold`} />
      </span>
      <span className={`flex flex-col ${column}`}>
        <span className={`${cell} bg-in-saffron`} />
        <span className={`${cell} grid place-items-center bg-white`}>
          {size === "md" && (
            <span className="border-in-chakra size-[5px] rounded-full border" />
          )}
        </span>
        <span className={`${cell} bg-in-green`} />
      </span>
    </span>
  );
}

/**
 * The page footer. Caveats live here once, as a single asterisk note, instead
 * of as warnings across the content; the asterisks in the content link to the
 * same explanation.
 */
export function SiteFooter({ compact = false }: { compact?: boolean }) {
  const top = compact ? "pt-12" : "pt-[clamp(64px,8vw,120px)]";
  return (
    <footer
      className={`mx-auto w-full max-w-[1320px] px-[clamp(20px,5vw,72px)] ${top} pb-10`}
    >
      <div className="border-ink h-[5px] border-t-2 border-b" />
      <div className="flex flex-wrap items-start justify-between gap-x-10 gap-y-5 py-6">
        <div className="flex flex-col gap-1.5">
          <Link href="/" className="text-ink text-base font-semibold">
            Vilayat · <span lang="hi">विलायत</span>
          </Link>
          <span className="text-ink-2 text-[13px]">
            India to Germany student relocation
          </span>
        </div>
        <nav aria-label="About this site">
          <ul className="grid grid-cols-2 gap-x-10 gap-y-2 text-[14px] sm:grid-cols-3">
            {INFO_PAGES.map((page) => (
              <li key={page.href}>
                <Link
                  href={page.href}
                  className="text-ink-2 hover:text-accent-strong"
                >
                  {page.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
      <p className="text-muted pb-5 text-[12px] leading-relaxed">
        * Placeholder figure.{" "}
        <Link
          href="/data#placeholder"
          className="hover:text-accent-strong underline underline-offset-2"
        >
          What this means
        </Link>
        . Information only, not legal or visa advice.
      </p>
      <FlagStripe height="h-1" />
    </footer>
  );
}

/**
 * The information pages as one quiet line, for the planner, whose map fills
 * the screen and leaves no room for the full footer.
 */
export function InfoLinks() {
  return (
    <nav aria-label="About this site" className="text-muted text-xs">
      <ul className="flex flex-wrap gap-x-3 gap-y-1">
        {INFO_PAGES.map((page) => (
          <li key={page.href}>
            <Link href={page.href} className="hover:text-accent-strong">
              {page.label}
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-1.5">
        * Placeholder figure,{" "}
        <Link href="/data#placeholder" className="underline underline-offset-2">
          see Data and sources
        </Link>
        .
      </p>
    </nav>
  );
}

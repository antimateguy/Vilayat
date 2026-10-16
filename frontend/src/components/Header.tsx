"use client";

import Link from "next/link";

import { FlagStripe, LogoMark } from "@/components/brand";
import { useAiStatus } from "@/lib/api/hooks";

type View = "planner" | "compare" | "ask";

interface HeaderProps {
  /** The working view on show; left out on the information pages. */
  current?: View;
  /** Query string carried to the other views, so the budget travels with the student. */
  query?: string;
}

const VIEWS: { id: View; label: string; href: string; needsModel?: boolean }[] =
  [
    { id: "planner", label: "Planner", href: "/planner" },
    { id: "compare", label: "Compare", href: "/compare" },
    { id: "ask", label: "Ask", href: "/ask", needsModel: true },
  ];

/** The bar at the top of the three working views. The logo leads home. */
export function Header({ current, query = "" }: HeaderProps) {
  const suffix = query ? `?${query}` : "";
  // Without a language model the question view has nothing to offer, so its
  // link is left out. The page a student is already on stays reachable.
  const modelEnabled = useAiStatus().data?.enabled === true;
  const views = VIEWS.filter(
    (view) => !view.needsModel || modelEnabled || view.id === current,
  );

  return (
    <header className="bg-page">
      <FlagStripe height="h-1" />
      <div className="border-hairline flex items-center gap-6 border-b px-4 py-3 md:px-7">
        <Link
          href="/"
          title="Back to the home page"
          className="mr-auto flex min-w-0 items-center gap-3"
        >
          <LogoMark size="sm" />
          <span className="text-[22px] leading-none font-semibold tracking-tight">
            Vilayat
          </span>
          <span className="text-ink-2 hidden truncate text-[13px] lg:block">
            Neighbourhoods that fit your rent, your commute and a part-time job
          </span>
        </Link>
        <nav aria-label="Views" className="flex shrink-0 gap-5">
          {views.map((view) =>
            view.id === current ? (
              <span
                key={view.id}
                aria-current="page"
                className="border-accent border-b-2 px-0.5 py-1.5 text-[15px]"
              >
                {view.label}
              </span>
            ) : (
              <Link
                key={view.id}
                href={`${view.href}${suffix}`}
                className="text-ink-2 hover:text-accent border-b-2 border-transparent px-0.5 py-1.5 text-[15px]"
              >
                {view.label}
              </Link>
            ),
          )}
        </nav>
      </div>
    </header>
  );
}

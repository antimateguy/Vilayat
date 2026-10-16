"use client";

import Link from "next/link";

import { FlagStripe, LogoMark, SiteFooter } from "@/components/brand";
import { ArrowDown } from "@/components/icons";
import { useAiStatus } from "@/lib/api/hooks";

import { HeroPhotos } from "./HeroPhotos";
import { PlanSection } from "./PlanSection";
import { Story } from "./Story";

const scrollToPlan = () =>
  document.getElementById("plan")?.scrollIntoView({ behavior: "smooth" });

/** The landing page: what Vilayat is, then the planner and question cards. */
export function HomePage() {
  const askEnabled = useAiStatus().data?.enabled === true;

  return (
    <div className="flex min-h-dvh flex-col">
      <FlagStripe />
      <header className="mx-auto flex w-full max-w-[1320px] flex-wrap items-center gap-x-7 gap-y-3 px-[clamp(20px,5vw,72px)] py-5">
        <Link href="/" className="mr-auto flex items-center gap-3.5">
          <LogoMark />
          <span className="flex flex-col items-start">
            <span className="text-[28px] leading-none font-semibold tracking-[-0.02em]">
              Vilayat
            </span>
            <span className="text-ink-2 mt-1.5 text-[11px] tracking-[0.1em] uppercase">
              India to Germany · student relocation
            </span>
          </span>
        </Link>
        <nav aria-label="Views" className="flex items-center gap-7">
          <Link href="/planner" className="hover:text-accent text-base">
            Planner
          </Link>
          <Link href="/compare" className="hover:text-accent text-base">
            Compare
          </Link>
          {askEnabled && (
            <Link href="/ask" className="hover:text-accent text-base">
              Ask
            </Link>
          )}
          <button
            type="button"
            onClick={scrollToPlan}
            className="btn btn-primary"
          >
            Plan my move
          </button>
        </nav>
      </header>

      <main>
        <section className="mx-auto max-w-[1320px] px-[clamp(20px,5vw,72px)] pt-[clamp(32px,5vw,72px)]">
          <div className="flex flex-wrap items-end gap-x-[clamp(32px,5vw,88px)] gap-y-12">
            <div className="min-w-0 flex-[1_1_560px]">
              <h1 className="-ml-[0.035em] text-[clamp(42px,5.3vw,84px)] leading-[1.04] tracking-[-0.025em]">
                <span className="block">
                  Germany said{" "}
                  <em
                    lang="de"
                    className="text-de-red relative inline-block font-normal"
                  >
                    ja.
                    <span
                      aria-hidden
                      className="absolute right-[0.3em] -bottom-[0.02em] left-[0.04em] flex h-[0.08em]"
                    >
                      <span className="bg-de-black flex-1" />
                      <span className="bg-de-red flex-1" />
                      <span className="bg-de-gold flex-1" />
                    </span>
                  </em>
                </span>
                <span className="block">Now find a room</span>
                <span className="block">
                  that fits<span className="text-in-saffron">.</span>
                </span>
              </h1>
              <p className="text-ink-2 mt-8 max-w-[52ch] text-[19px] leading-relaxed">
                Vilayat shows Indian students which Berlin and Munich
                neighbourhoods fit their rent, their commute to campus and a
                part-time job — then answers the paperwork from official
                documents, with every source named.
              </p>
              <div className="mt-8 flex flex-wrap gap-4">
                <button
                  type="button"
                  onClick={scrollToPlan}
                  className="btn btn-primary px-5 py-3 text-base"
                >
                  Plan my move <ArrowDown size={18} />
                </button>
                {askEnabled && (
                  <Link
                    href="/ask"
                    className="btn btn-ghost px-2.5 py-3 text-base"
                  >
                    Ask about the paperwork
                  </Link>
                )}
              </div>
            </div>
            <HeroPhotos />
          </div>
        </section>

        <Story />
        <PlanSection />
      </main>

      <SiteFooter />
    </div>
  );
}

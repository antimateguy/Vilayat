"use client";

import { type ReactNode, useEffect, useRef } from "react";

import { ArrowRight, Campus, Euro, MapIcon, Train } from "@/components/icons";

// What / Why / How, told as the page scrolls. On wide screens the section is
// pinned while three panels hand over to each other; on phones, and for
// visitors who ask for reduced motion, the panels are simply stacked.

const MOTION_QUERY =
  "(min-width: 900px) and (prefers-reduced-motion: no-preference)";

interface Chapter {
  number: string;
  rail: [string, string];
  kicker: string;
  kickerClass: string;
  barClass: string;
  numberShadow: string;
  title: string;
  body: string;
  extra: ReactNode;
}

const TERMS: [string, string, string][] = [
  ["Anmeldung", "register your address within two weeks", "bg-[#f3e2b0]"],
  ["Sperrkonto", "the blocked account", "bg-[#f0d2d6]"],
  ["Rundfunkbeitrag", "the broadcasting fee", "bg-[#dedcdb]"],
  ["Aufenthaltstitel", "the residence permit", "bg-[#f3e2b0]"],
  ["WG-Casting", "the flat-share interview", "bg-[#f0d2d6]"],
  ["Kaution", "a deposit of two to three months’ rent", "bg-[#dedcdb]"],
];

const STEPS: [ReactNode, string][] = [
  [<Campus key="c" size={22} />, "Your campus"],
  [<Euro key="e" size={22} />, "What you can pay"],
  [<Train key="t" size={22} />, "How far you’ll ride"],
  [<MapIcon key="m" size={22} />, "Every area, ranked — with reasons"],
];

const CHAPTERS: Chapter[] = [
  {
    number: "01",
    rail: ["What", "The problem"],
    kicker: "What — the problem",
    kickerClass: "text-de-red",
    barClass: "bg-de-red",
    numberShadow: "0.03em 0.02em 0 #c8102e, -0.025em -0.015em 0 #f2b705",
    title: "A visa, a campus, and nowhere to live.",
    body: "Listings are in German and gone within a day. The cheap room turns out to be ninety minutes from campus. Then comes the paperwork — each word its own office and deadline, explained differently on every forum.",
    extra: (
      <div className="mt-6 flex max-w-[820px] flex-wrap gap-2.5">
        {TERMS.map(([word, meaning, colour], i) => (
          <span
            key={word}
            data-reveal
            style={{ rotate: `${[-1.5, 1, -0.5, 1.5, -1, 0.5][i]}deg` }}
            className={`flex items-baseline gap-2 rounded-[2px] px-3 py-1.5 ${colour}`}
          >
            <em lang="de" className="text-lg leading-tight">
              {word}
            </em>
            <span className="text-ink-2 text-[13px]">{meaning}</span>
          </span>
        ))}
      </div>
    ),
  },
  {
    number: "02",
    rail: ["Why", "Vilayat"],
    kicker: "Why — Vilayat",
    kickerClass: "text-saffron-ink",
    barClass: "bg-in-saffron",
    numberShadow: "0.03em 0.02em 0 #e98a1f, -0.025em -0.015em 0 #127a0a",
    title: "Built from your campus outward.",
    body: "Vilayat starts with where you study and what you can pay, and works out every neighbourhood that fits — ranked by commute, rent, everyday amenities and part-time work nearby. It tells you why an area ranks where it does, and what you give up for it.",
    extra: (
      <div className="mt-7 flex flex-wrap items-center gap-3">
        {STEPS.map(([icon, label], i) => (
          <span key={label} data-reveal className="flex items-center gap-3">
            <span className="bg-surface flex items-center gap-2.5 rounded-[2px] px-3.5 py-2">
              <span className={i % 2 ? "text-saffron-ink" : "text-in-green"}>
                {icon}
              </span>
              <span className="text-[17px] font-semibold">{label}</span>
            </span>
            {i < STEPS.length - 1 && (
              <span className="text-saffron-ink">
                <ArrowRight size={20} />
              </span>
            )}
          </span>
        ))}
      </div>
    ),
  },
  {
    number: "03",
    rail: ["How", "It works"],
    kicker: "How — it works",
    kickerClass: "text-in-green",
    barClass: "bg-in-green",
    numberShadow: "0.03em 0.02em 0 #c8102e, -0.025em -0.015em 0 #127a0a",
    title: "Three steps, one evening.",
    body: "No listings to scroll and no agents. Set your limits once, read the map, and get the rules from the documents themselves.",
    extra: (
      <ol className="mt-7 flex max-w-[640px] flex-col gap-4">
        {[
          [
            "text-de-red",
            "Describe your campus, budget and commute limit — in one sentence, if you like.",
          ],
          [
            "text-saffron-ink",
            "See every area ranked on the map, with the reasoning beside it.",
          ],
          [
            "text-in-green",
            "Ask about registration, permits or work rules; every answer names the document it comes from.",
          ],
        ].map(([colour, text], i) => (
          <li
            key={text}
            data-reveal
            className="flex items-baseline gap-5 text-lg leading-snug"
          >
            <span
              className={`min-w-[0.8em] text-4xl leading-none font-semibold ${colour}`}
            >
              {i + 1}
            </span>
            <span>{text}</span>
          </li>
        ))}
      </ol>
    ),
  },
];

export function Story() {
  const section = useRef<HTMLElement>(null);
  const panels = useRef<(HTMLDivElement | null)[]>([]);
  const rails = useRef<(HTMLButtonElement | null)[]>([]);
  const bars = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    const media = window.matchMedia(MOTION_QUERY);
    let frame = 0;
    const clamp = (value: number) => Math.max(0, Math.min(1, value));

    const update = () => {
      frame = 0;
      const box = section.current;
      if (!box) return;
      const animate = media.matches;
      const total = Math.max(1, box.offsetHeight - window.innerHeight);
      const progress = clamp(-box.getBoundingClientRect().top / total) * 3;

      panels.current.forEach((panel, i) => {
        if (!panel) return;
        const reveals = panel.querySelectorAll<HTMLElement>("[data-reveal]");
        if (!animate) {
          panel.style.cssText = "";
          reveals.forEach((item) => {
            item.style.opacity = "";
            item.style.translate = "";
          });
          return;
        }
        const local = progress - i;
        const enter = i === 0 ? 1 : clamp(local / 0.12);
        const exit = i === CHAPTERS.length - 1 ? 1 : clamp((1 - local) / 0.12);
        const opacity = Math.min(enter, exit);
        panel.style.opacity = String(opacity);
        panel.style.transform = `translateY(${(1 - enter) * 48 - (1 - exit) * 48}px)`;
        panel.style.visibility = opacity < 0.01 ? "hidden" : "visible";
        panel.style.pointerEvents = opacity > 0.5 ? "auto" : "none";
        reveals.forEach((item, j) => {
          const start = 0.06 + j * (0.5 / Math.max(1, reveals.length));
          const shown = clamp((local - start) / 0.08);
          item.style.opacity = String(shown);
          item.style.translate = `0 ${(1 - shown) * 18}px`;
        });
        const bar = bars.current[i];
        if (bar) bar.style.width = `${clamp(local) * 100}%`;
        const rail = rails.current[i];
        if (rail) {
          const active = local >= 0 && (local < 1 || i === CHAPTERS.length - 1);
          rail.style.opacity = active ? "1" : "0.45";
        }
      });
    };
    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    media.addEventListener("change", schedule);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      media.removeEventListener("change", schedule);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  const jumpTo = (i: number) => {
    const box = section.current;
    if (!box) return;
    if (!window.matchMedia(MOTION_QUERY).matches) {
      panels.current[i]?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    const top = box.getBoundingClientRect().top + window.scrollY;
    const total = box.offsetHeight - window.innerHeight;
    window.scrollTo({
      top: top + total * (i / 3) + (i ? total * 0.05 : 0),
      behavior: "smooth",
    });
  };

  return (
    <section
      ref={section}
      aria-label="What Vilayat does"
      className="relative mt-16 min-[900px]:h-[360vh]"
    >
      <div className="mx-auto flex max-w-[1320px] flex-col px-[clamp(20px,5vw,72px)] pt-6 pb-8 min-[900px]:sticky min-[900px]:top-0 min-[900px]:h-dvh">
        <div className="border-ink h-[5px] border-t-2 border-b" />
        <p className="text-ink-2 flex flex-wrap justify-between gap-x-7 gap-y-3 py-3.5 text-[13px] tracking-[0.08em] uppercase">
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <span>Vilayat</span>
            <span aria-hidden className="bg-in-saffron size-1.5 rounded-full" />
            <span lang="hi" className="text-[15px] tracking-normal normal-case">
              विलायत
            </span>
            <span
              aria-hidden
              className="ring-in-chakra size-1.5 rounded-full bg-white ring-1"
            />
            <span lang="pa" className="text-[15px] tracking-normal normal-case">
              ਵਿਲਾਇਤ
            </span>
            <span aria-hidden className="bg-in-green size-1.5 rounded-full" />
            <span
              lang="ur"
              dir="rtl"
              className="text-[15px] tracking-normal normal-case"
            >
              ولایت
            </span>
            <span aria-hidden className="bg-de-red size-1.5 rounded-full" />
            <span>“abroad”</span>
          </span>
          <span className="flex items-center gap-2">
            <span aria-hidden className="bg-de-red size-2 rounded-full" />
            Rent · Commute · Campus · Jobs · Paperwork
            <span aria-hidden className="bg-in-green size-2 rounded-full" />
          </span>
        </p>
        <div className="border-ink border-t" />

        <div className="grid min-h-0 flex-1 items-center gap-[clamp(28px,5vw,88px)] pt-4 min-[900px]:grid-cols-[minmax(150px,240px)_minmax(0,1fr)]">
          <div className="hidden flex-col gap-8 min-[900px]:flex">
            {CHAPTERS.map((chapter, i) => (
              <button
                key={chapter.number}
                ref={(el) => {
                  rails.current[i] = el;
                }}
                type="button"
                onClick={() => jumpTo(i)}
                className="flex flex-col items-start gap-1 text-left transition-opacity"
                style={{ opacity: i === 0 ? 1 : 0.45 }}
              >
                <span className="text-ink-2 text-[13px] tracking-widest">
                  {chapter.number}
                </span>
                <span className="text-[26px] leading-tight font-semibold">
                  {chapter.rail[0]}
                </span>
                <span className="text-ink-2 text-sm">{chapter.rail[1]}</span>
                <span className="bg-hairline mt-2 block h-[3px] w-full">
                  <span
                    ref={(el) => {
                      bars.current[i] = el;
                    }}
                    className={`block h-[3px] w-0 ${chapter.barClass}`}
                  />
                </span>
              </button>
            ))}
          </div>

          <div className="relative flex h-full min-h-0 flex-col gap-20 min-[900px]:block">
            {CHAPTERS.map((chapter, i) => (
              <div
                key={chapter.number}
                ref={(el) => {
                  panels.current[i] = el;
                }}
                className="flex scroll-mt-6 flex-col justify-center min-[900px]:absolute min-[900px]:inset-0"
              >
                <div className="flex items-end gap-[clamp(16px,2.5vw,36px)]">
                  <div
                    aria-hidden
                    className="flex-none text-[clamp(56px,min(9vw,15vh),140px)] leading-[0.9] font-semibold tracking-[-0.04em]"
                    style={{ textShadow: chapter.numberShadow }}
                  >
                    {chapter.number}
                  </div>
                  <div className="min-w-0">
                    <span className={`kicker mb-3.5 ${chapter.kickerClass}`}>
                      {chapter.kicker}
                    </span>
                    <h2 className="max-w-[17ch] text-[clamp(28px,min(4.2vw,6.6vh),58px)] leading-[1.06] tracking-[-0.02em]">
                      {chapter.title}
                    </h2>
                  </div>
                </div>
                <p className="text-ink-2 mt-5 max-w-[56ch] text-[clamp(15px,2.1vh,18px)] leading-relaxed">
                  {chapter.body}
                </p>
                {chapter.extra}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

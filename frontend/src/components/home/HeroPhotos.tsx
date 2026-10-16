"use client";

import { useEffect, useState } from "react";

import { HERO_ORDER, nextIndex, UNIVERSITY_PHOTOS } from "@/lib/universities";

const SECONDS_PER_PHOTO = 5;

/**
 * The universities' photographs, one at a time, fading from one to the next.
 * The cycle pauses while the pointer or keyboard focus is on it, and does not
 * run at all for visitors who ask for reduced motion.
 */
export function HeroPhotos() {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(
      () => setIndex((current) => nextIndex(current, HERO_ORDER.length)),
      SECONDS_PER_PHOTO * 1000,
    );
    return () => window.clearInterval(timer);
  }, [paused]);

  const current = UNIVERSITY_PHOTOS[HERO_ORDER[index]];

  return (
    <figure
      className="flex min-w-[260px] flex-[0_1_400px] flex-col gap-2"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className="flex gap-1.5">
        <div className="halftone relative aspect-square flex-1">
          {HERO_ORDER.map((key, position) => {
            const photo = UNIVERSITY_PHOTOS[key];
            return (
              // eslint-disable-next-line @next/next/no-img-element -- a static export has no image optimiser
              <img
                key={key}
                src={photo.src}
                alt={position === index ? photo.alt : ""}
                aria-hidden={position !== index}
                loading={position === 0 ? "eager" : "lazy"}
                className={`absolute inset-0 size-full object-cover transition-opacity duration-1000 ${
                  position === index ? "opacity-100" : "opacity-0"
                }`}
              />
            );
          })}
        </div>
        <div aria-hidden className="flex w-2.5 flex-col">
          <span className="bg-in-saffron flex-1" />
          <span className="grid flex-1 place-items-center bg-white">
            <span className="border-in-chakra size-[7px] rounded-full border-[1.5px]" />
          </span>
          <span className="bg-in-green flex-1" />
        </div>
      </div>
      <figcaption className="text-ink-2 flex items-start justify-between gap-3 text-xs leading-snug">
        <span aria-live="polite">
          <span className="text-ink font-semibold">{HERO_ORDER[index]}</span>
          {" · "}
          {current.alt}
        </span>
        <a
          href={current.source}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 underline"
        >
          Photo: {current.credit}
        </a>
      </figcaption>
      <div className="flex gap-1.5" role="group" aria-label="Choose a photo">
        {HERO_ORDER.map((key, position) => (
          <button
            key={key}
            type="button"
            onClick={() => setIndex(position)}
            aria-label={`Show ${key}`}
            aria-pressed={position === index}
            className={`h-1 flex-1 rounded-full ${
              position === index ? "bg-ink" : "bg-axis hover:bg-ink-2"
            }`}
          />
        ))}
      </div>
    </figure>
  );
}

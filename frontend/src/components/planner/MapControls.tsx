"use client";

import { NEUTRAL, overlayScale, SCORE_COLOURS } from "@/lib/map-style";
import { type Overlay, OVERLAYS } from "@/lib/search-state";

import type { MapExtras } from "./MapView";

const OVERLAY_LABELS: Record<Overlay, string> = {
  none: "Ranking",
  commute: "Commute",
  amenities: "Amenities",
  job_access: "Jobs",
};

/** Chooses what the map is shaded by. */
export function LayerSwitch({
  overlay,
  commuteAvailable,
  onChange,
}: {
  overlay: Overlay;
  commuteAvailable: boolean;
  onChange: (overlay: Overlay) => void;
}) {
  return (
    <fieldset className="border-hairline bg-page inline-flex overflow-hidden rounded-[2px] border shadow-(--shadow-float)">
      <legend className="sr-only">Shade the map by</legend>
      {OVERLAYS.map((option) => {
        const disabled = option === "commute" && !commuteAvailable;
        return (
          <label
            key={option}
            className={`px-2.5 py-1.5 text-sm has-focus-visible:outline-2 ${
              overlay === option
                ? "bg-accent text-page font-medium"
                : disabled
                  ? "text-muted cursor-not-allowed"
                  : "text-ink-2 hover:text-ink cursor-pointer"
            }`}
          >
            <input
              type="radio"
              name="map-layer"
              value={option}
              checked={overlay === option}
              disabled={disabled}
              onChange={() => onChange(option)}
              className="sr-only"
            />
            {OVERLAY_LABELS[option]}
          </label>
        );
      })}
    </fieldset>
  );
}

/** Says what the colours on the map mean. Always present. */
export function Legend({ overlay }: { overlay: Overlay }) {
  return (
    <div className="bg-page max-w-56 rounded-[2px] px-3 py-2 text-xs shadow-(--shadow-float)">
      {overlay === "none" ? (
        <RankingLegend />
      ) : (
        <BandLegend overlay={overlay} />
      )}
    </div>
  );
}

function Swatch({ colour, outlined }: { colour: string; outlined?: boolean }) {
  return (
    <span
      aria-hidden
      className="inline-block size-3 shrink-0 rounded-sm"
      style={
        outlined
          ? {
              border: `1px solid ${NEUTRAL.outline}`,
              background: "transparent",
            }
          : { background: colour }
      }
    />
  );
}

function RankingLegend() {
  return (
    <>
      <p className="font-medium">Areas within your limits</p>
      <div className="mt-1.5 flex items-center gap-1.5">
        <span className="text-ink-2">Lower rank</span>
        <span className="flex gap-0.5">
          {SCORE_COLOURS.map((colour) => (
            <Swatch key={colour} colour={colour} />
          ))}
        </span>
        <span className="text-ink-2">Best</span>
      </div>
      <ul className="text-ink-2 mt-1.5 flex flex-col gap-1">
        <li className="flex items-center gap-1.5">
          <Swatch colour={NEUTRAL.excluded} /> Outside your limits
        </li>
        <li className="flex items-center gap-1.5">
          <Swatch colour="" outlined /> Cannot be checked
        </li>
      </ul>
    </>
  );
}

function BandLegend({ overlay }: { overlay: Exclude<Overlay, "none"> }) {
  const scale = overlayScale(overlay);
  return (
    <>
      <p className="font-medium">{scale.title}</p>
      <p className="text-ink-2">{scale.note}</p>
      <ul className="mt-1.5 flex flex-col gap-1">
        {[...scale.bands].reverse().map((band) => (
          <li key={band.label} className="flex items-center gap-1.5">
            <Swatch colour={band.colour} /> {band.label}
          </li>
        ))}
        <li className="text-ink-2 flex items-center gap-1.5">
          <Swatch colour="" outlined /> No figure
        </li>
      </ul>
    </>
  );
}

const EXTRAS: {
  key: keyof MapExtras;
  emoji: string;
  label: string;
  title: string;
}[] = [
  {
    key: "universities",
    emoji: "🎓",
    label: "Universities",
    title: "Show every campus; click one to choose it",
  },
  {
    key: "employers",
    emoji: "💼",
    label: "Employers",
    title: "Show the employers; click one to pin it",
  },
  {
    key: "transit",
    emoji: "🚇",
    label: "Lines",
    title: "Show the U-Bahn, S-Bahn and tram lines",
  },
];

/** Overlays the student can add on top of any layer. */
export function MapExtrasBar({
  extras,
  onToggle,
}: {
  extras: MapExtras;
  onToggle: (key: keyof MapExtras) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Show on the map"
      className="flex flex-wrap gap-1.5"
    >
      {EXTRAS.map(({ key, emoji, label, title }) => (
        <button
          key={key}
          type="button"
          aria-pressed={extras[key]}
          title={title}
          onClick={() => onToggle(key)}
          className={`rounded-[2px] border px-2 py-1 text-xs shadow-(--shadow-float) ${
            extras[key]
              ? "border-accent-soft bg-accent-wash text-accent-strong font-medium"
              : "border-hairline bg-page text-ink-2 hover:text-ink"
          }`}
        >
          <span aria-hidden className="mr-1">
            {emoji}
          </span>
          {label}
        </button>
      ))}
    </div>
  );
}

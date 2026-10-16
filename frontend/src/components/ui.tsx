// Small shared pieces of the interface.

import Link from "next/link";

import { ApiError } from "@/lib/api/client";

/**
 * Marks placeholder data with a small asterisk instead of a warning box. The
 * asterisk links to the page that explains what is placeholder and why, and
 * screen readers hear the words, not the symbol.
 */
export function SampleMark({ what = "placeholder data" }: { what?: string }) {
  return (
    <Link
      href="/data#placeholder"
      title={`${what[0].toUpperCase()}${what.slice(1)}: see Data and sources`}
      className="text-ink-2 hover:text-accent-strong ml-0.5 align-super text-[0.75em] leading-none no-underline"
    >
      <span aria-hidden>*</span>
      <span className="sr-only">({what}, see Data and sources)</span>
    </Link>
  );
}

/** A figure the app does not have. Worded, and visually set apart from real values. */
export function Unknown({ what }: { what?: string }) {
  return (
    <span className="text-muted italic" title="This figure is not available">
      Unknown{what ? ` ${what}` : ""}
    </span>
  );
}

/** A 0 to 1 value as a thin bar on a lighter track of the same hue. */
export function Meter({ value, label }: { value: number; label: string }) {
  const percent = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      aria-label={label}
      className="bg-accent-wash h-1.5 w-full overflow-hidden rounded-full"
    >
      <div
        className="bg-accent h-full rounded-r-full"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

export function ErrorMessage({ error }: { error: unknown }) {
  const api = error instanceof ApiError ? error : null;
  return (
    <div
      role="alert"
      className="border-critical/40 rounded-[2px] border px-3 py-2 text-sm"
    >
      <p className="font-medium">
        {api?.code === "rate_limited"
          ? "Too many requests. Wait a moment and try again."
          : (api?.message ?? "Something went wrong.")}
      </p>
      {api?.details.map((detail) => (
        <p key={detail.field} className="text-ink-2">
          {detail.field}: {detail.problem}
        </p>
      ))}
      {api?.requestId && (
        <p className="text-muted mt-1 text-xs">Request ID {api.requestId}</p>
      )}
    </div>
  );
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="field-label font-normal">{children}</h2>;
}

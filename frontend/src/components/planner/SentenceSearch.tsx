"use client";

import { useId, useState } from "react";

import { Sparkle } from "@/components/icons";
import { ErrorMessage } from "@/components/ui";
import { aiState, formatReset } from "@/lib/ai-status";
import { ApiError } from "@/lib/api/client";
import { useAiStatus, useIntent } from "@/lib/api/hooks";
import type { City } from "@/lib/api/schemas";
import { type AppliedIntent, applyIntent } from "@/lib/intent";
import type { SearchState } from "@/lib/search-state";

const MIN_LENGTH = 3;
const MAX_LENGTH = 500;

interface SentenceSearchProps {
  state: SearchState;
  cities: City[];
  onApply: (changes: Partial<SearchState>) => void;
}

/**
 * Lets the student describe the search in a sentence. A language model reads
 * the sentence; the result only moves the controls below, which the student can
 * see and correct. Hidden entirely when no model is configured.
 */
export function SentenceSearch({
  state,
  cities,
  onApply,
}: SentenceSearchProps) {
  const field = useId();
  const status = useAiStatus();
  const intent = useIntent();
  const [sentence, setSentence] = useState("");
  const [outcome, setOutcome] = useState<AppliedIntent | null>(null);

  const ai = aiState(status.data);
  if (ai === undefined || ai === "off") return null;
  if (ai === "resting") {
    return (
      <p className="text-ink-2 text-sm">
        Sentence search is paused until{" "}
        {formatReset(status.data?.resets_at ?? null)}: today&apos;s free AI
        allowance is used up. The controls below work as usual.
      </p>
    );
  }

  const submit = () => {
    const text = sentence.trim();
    if (text.length < MIN_LENGTH || intent.isPending) return;
    setOutcome(null);
    intent.mutate(
      { sentence: text, city: state.city },
      {
        onSuccess: (found) => {
          const applied = applyIntent(state, found, cities);
          onApply(applied.changes);
          setOutcome(applied);
        },
      },
    );
  };

  const unavailable =
    intent.error instanceof ApiError && intent.error.code === "ai_unavailable";

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label htmlFor={field} className="field-label">
        Describe what you need
      </label>
      <textarea
        id={field}
        rows={2}
        maxLength={MAX_LENGTH}
        value={sentence}
        onChange={(event) => setSentence(event.target.value)}
        onKeyDown={(event) => {
          // Enter sends, Shift+Enter starts a new line.
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        placeholder="I study at TUM, can pay 700 EUR and want at most 30 minutes to campus."
        className="input resize-none text-[15px]"
      />
      <div className="flex items-center justify-between gap-3">
        <p className="text-ink-2 text-xs leading-snug">
          An AI model reads the sentence and fills in the controls below. The
          ranking is computed without it.
        </p>
        <button
          type="submit"
          disabled={sentence.trim().length < MIN_LENGTH || intent.isPending}
          className="btn btn-secondary shrink-0"
        >
          <Sparkle size={16} />
          {intent.isPending ? "Reading…" : "Fill in"}
        </button>
      </div>

      <div aria-live="polite" className="flex flex-col gap-1.5 empty:hidden">
        {outcome && outcome.applied.length > 0 && (
          <div className="text-sm">
            <p className="font-medium">Filled in from your sentence</p>
            <ul className="text-ink-2 mt-0.5 list-disc pl-5">
              {outcome.applied.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        )}
        {outcome && outcome.applied.length === 0 && (
          <p className="text-sm">
            Nothing in that sentence could be turned into a setting. Use the
            controls below.
          </p>
        )}
        {outcome && outcome.notes.length > 0 && (
          <ul className="text-ink-2 flex flex-col gap-0.5 text-sm">
            {outcome.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        )}
        {unavailable && (
          <p className="text-sm">
            The sentence search is not available right now. The controls below
            work as usual.
          </p>
        )}
        {intent.isError && !unavailable && (
          <ErrorMessage error={intent.error} />
        )}
      </div>
    </form>
  );
}

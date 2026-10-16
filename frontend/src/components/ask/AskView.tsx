"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { SiteFooter } from "@/components/brand";
import { Header } from "@/components/Header";
import { ErrorMessage, SampleMark, SectionTitle } from "@/components/ui";
import { aiState, formatReset } from "@/lib/ai-status";
import { ApiError } from "@/lib/api/client";
import { useAiStatus, useAsk, useCities } from "@/lib/api/hooks";
import type { Answer, Citation } from "@/lib/api/schemas";
import { splitCitations } from "@/lib/citations";
import { formatDate } from "@/lib/format";
import {
  DEFAULT_STATE,
  parseSearchState,
  toSearchParams,
} from "@/lib/search-state";

const MIN_LENGTH = 3;
const MAX_LENGTH = 300;
const EXAMPLES = [
  "How soon must I register my address?",
  "How many days a year may I work as a student?",
  "How much is the broadcasting fee, and can flatmates share it?",
  "What do I need for the residence permit?",
];

export function AskView() {
  const field = useId();
  const initialParams = useSearchParams();
  const [city, setCity] = useState(
    () => parseSearchState(new URLSearchParams(initialParams.toString())).city,
  );
  // A question handed over from the home page arrives in the address as ?q=.
  const handedOver = initialParams.get("q")?.trim() ?? "";
  const [question, setQuestion] = useState(handedOver);
  const status = useAiStatus();
  const cities = useCities();
  const ask = useAsk();

  const send = (text: string) => {
    const trimmed = text.trim();
    if (trimmed.length < MIN_LENGTH || ask.isPending) return;
    setQuestion(trimmed);
    ask.mutate({ question: trimmed, city });
  };

  // Ask the handed-over question once, as soon as it is known that a model is
  // there to answer it.
  const askedOnArrival = useRef(false);
  useEffect(() => {
    if (askedOnArrival.current || !handedOver || aiState(status.data) !== "on")
      return;
    askedOnArrival.current = true;
    ask.mutate({ question: handedOver, city });
  }, [handedOver, status.data, ask, city]);

  const query = toSearchParams({ ...DEFAULT_STATE, city }).toString();
  const unavailable =
    ask.error instanceof ApiError && ask.error.code === "ai_unavailable";
  const state = aiState(status.data);

  return (
    <div className="flex min-h-dvh flex-col">
      <Header current="ask" query={query} />
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 md:px-12">
        <div>
          <h1 className="text-4xl tracking-tight">Questions about moving</h1>
          <p className="text-ink-2 mt-2.5 text-base leading-relaxed">
            Answers are written by an AI model from the documents stored in
            Vilayat, and every statement names its source. If the documents do
            not cover a question, you are told so.
          </p>
        </div>

        {state === "off" ? (
          <p className="border-hairline rounded-[2px] border px-3 py-2 text-sm">
            Questions are switched off because no AI model is configured. The
            planner and the comparison work as usual.
          </p>
        ) : state === "resting" ? (
          <p className="border-hairline rounded-[2px] border px-3 py-2 text-sm">
            Today&apos;s free allowance for AI answers is used up, so questions
            are paused until {formatReset(status.data?.resets_at ?? null)}. The
            planner and the comparison work as usual.
          </p>
        ) : (
          <>
            <form
              className="flex flex-col gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                send(question);
              }}
            >
              <fieldset>
                <legend className="mb-1.5">
                  <SectionTitle>City</SectionTitle>
                </legend>
                <div className="border-hairline inline-flex overflow-hidden rounded-[2px] border">
                  {(cities.data ?? []).map((item) => (
                    <label
                      key={item.id}
                      className={`cursor-pointer px-3 py-1.5 text-sm has-focus-visible:outline-2 ${
                        city === item.id
                          ? "bg-accent text-page font-medium"
                          : "bg-page text-ink hover:bg-surface"
                      }`}
                    >
                      <input
                        type="radio"
                        name="city"
                        value={item.id}
                        checked={city === item.id}
                        onChange={() => setCity(item.id)}
                        className="sr-only"
                      />
                      {item.name}
                    </label>
                  ))}
                </div>
                <p className="text-muted mt-1 text-xs">
                  Documents about the other city are left out.
                </p>
              </fieldset>

              <div>
                <label htmlFor={field} className="mb-1.5 block">
                  <SectionTitle>Your question</SectionTitle>
                </label>
                <div className="flex gap-2">
                  <input
                    id={field}
                    type="text"
                    maxLength={MAX_LENGTH}
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="How soon must I register my address?"
                    className="input min-h-12 min-w-0 flex-1 text-base"
                  />
                  <button
                    type="submit"
                    disabled={
                      question.trim().length < MIN_LENGTH || ask.isPending
                    }
                    className="btn btn-primary min-h-12 shrink-0 px-5"
                  >
                    {ask.isPending ? "Looking…" : "Ask"}
                  </button>
                </div>
              </div>

              <ul className="flex flex-wrap gap-1.5">
                {EXAMPLES.map((example) => (
                  <li key={example}>
                    <button
                      type="button"
                      onClick={() => send(example)}
                      disabled={ask.isPending}
                      className="btn btn-secondary px-3 py-1.5 text-left text-[13px] font-normal"
                    >
                      {example}
                    </button>
                  </li>
                ))}
              </ul>
            </form>

            <div aria-live="polite" className="flex flex-col gap-4">
              {ask.isPending && (
                <p className="text-ink-2 text-sm">Looking in the documents…</p>
              )}
              {unavailable && (
                <p className="border-hairline rounded-[2px] border px-3 py-2 text-sm">
                  The assistant is not available right now. Try again in a
                  moment; the planner and the comparison work as usual.
                </p>
              )}
              {ask.isError && !unavailable && (
                <ErrorMessage error={ask.error} />
              )}
              {ask.data && !ask.isPending && <AnswerBlock answer={ask.data} />}
            </div>
          </>
        )}
      </main>
      <SiteFooter compact />
    </div>
  );
}

function AnswerBlock({ answer }: { answer: Answer }) {
  return (
    <>
      <div className="bg-surface rounded-[2px] px-5 py-4">
        <SectionTitle>
          {answer.status === "answered" ? "Answer" : "No answer"}
        </SectionTitle>
        <p className="mt-1 leading-relaxed">
          {answer.status === "answered"
            ? splitCitations(answer.answer).map((part, index) =>
                part.kind === "text" ? (
                  <span key={index}>{part.text}</span>
                ) : (
                  <a
                    key={index}
                    href={`#source-${part.number}`}
                    aria-label={`Source ${part.number}`}
                    className="text-accent-strong text-sm font-medium"
                  >
                    [{part.number}]
                  </a>
                ),
              )
            : answer.answer}
        </p>
        {answer.status === "answered" && (
          <p className="text-muted mt-2 text-xs">
            Written by an AI model from the sources below. Read the source
            before you rely on it.
          </p>
        )}
      </div>

      {answer.citations.length > 0 && (
        <div>
          <SectionTitle>
            {answer.status === "answered" ? "Sources" : "Closest passages"}
          </SectionTitle>
          <ol className="mt-2 flex flex-col gap-3">
            {answer.citations.map((citation) => (
              <Source key={citation.number} citation={citation} />
            ))}
          </ol>
        </div>
      )}
    </>
  );
}

function Source({ citation }: { citation: Citation }) {
  return (
    <li
      id={`source-${citation.number}`}
      className="border-hairline scroll-mt-4 rounded-[2px] border px-3 py-2 text-sm"
    >
      <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="text-ink-2 font-medium tabular-nums">
          [{citation.number}]
        </span>
        <a
          href={citation.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent-strong font-medium underline"
        >
          {citation.title}
        </a>
        {citation.is_sample && (
          <SampleMark what="a summary written for Vilayat, not the official text" />
        )}
      </p>
      <p className="text-ink-2 mt-0.5">
        {citation.section ? `${citation.section} · ` : ""}
        read on {formatDate(citation.retrieved_on)} · opens in a new tab
      </p>
      {citation.passage !== null ? (
        <details className="mt-1">
          <summary className="text-ink-2 cursor-pointer">
            Show the passage
          </summary>
          <p className="mt-1 whitespace-pre-line">{citation.passage}</p>
        </details>
      ) : (
        <p className="text-muted mt-1 text-xs">
          The official text is not reproduced here; follow the link to read it.
        </p>
      )}
    </li>
  );
}

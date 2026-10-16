import type { Metadata } from "next";
import Link from "next/link";

import { InfoPage } from "@/components/info/InfoPage";

export const metadata: Metadata = { title: "How we use AI · Vilayat" };

export default function AiPage() {
  return (
    <InfoPage
      kicker="How we use AI"
      title="The model explains; it does not decide"
      intro="Vilayat uses a language model in three places. In none of them does the model choose which area comes first: the ranking is ordinary code working on the data, and gives the same answer every time."
    >
      <h2>1. Turning your sentence into settings</h2>
      <p>
        On the planner you can type what you want, such as &ldquo;near LMU, at
        most 750 euros, 30 minutes&rdquo;. The model reads the sentence and
        fills in a form: campus, rent ceiling, travel limit and which priorities
        matter to you. The code then checks the form. A campus or employer the
        model names must exist in Vilayat&apos;s own list, and numbers must be
        within the allowed range; anything else is dropped and you are told what
        was not understood. You see the settings it chose and can change any of
        them.
      </p>

      <h2>2. Answering questions on Ask</h2>
      <p>
        Your question is compared with a stored set of documents, and only the
        closest passages are given to the model, with the instruction to answer
        from them alone and name the source of each statement. The answer is
        then checked before you see it:
      </p>
      <ul>
        <li>
          If no passage is close enough to the question, the model is not asked
          at all and you are told that the documents do not cover it.
        </li>
        <li>
          The answer must cite at least one passage, and every citation must
          point at a passage that was actually supplied.
        </li>
        <li>
          Every number in the answer, such as a fee, a deadline or a number of
          days, must appear in the cited passages.
        </li>
      </ul>
      <p>
        An answer that fails a check is withheld, and you get the matching
        passages and their links instead. Vilayat does not search the web, so it
        cannot answer from pages it has not stored. Which documents those are is
        explained on <Link href="/data#placeholder">Data and sources</Link>.
      </p>

      <h2>3. The short area summaries</h2>
      <p>
        The paragraph at the top of an area&apos;s details is written by the
        model in advance, from the figures the ranking uses, and checked before
        it is stored: every number must be one of those figures, and no other
        place name may appear. A summary that fails is rewritten once and
        otherwise dropped. When the underlying data changes, the old summary is
        no longer shown.
      </p>

      <h2>Which model</h2>
      <p>
        Vilayat uses Google&apos;s Gemini models through the Gemini API: a small
        text model (Gemini Flash-Lite) for the three tasks above, and a Gemini
        embedding model to compare questions with documents. What is sent to
        Google is described on <Link href="/privacy">Privacy</Link>.
      </p>

      <h2>A fixed daily allowance</h2>
      <p>
        Vilayat uses the free tier of the Gemini API, which allows a fixed
        number of requests per day. Every request is counted before it is sent,
        including the ones the offline jobs make, and when the day&apos;s
        allowance is used up no further request goes out. The sentence box and
        the Ask page then say when they are back: the allowance starts again at
        midnight Pacific time, which is 09:00 in Germany (08:00 for a few weeks
        in spring and autumn) and 12:30 or 13:30 in India.
      </p>

      <h2>When the model is unavailable</h2>
      <p>
        The planner, the map, the ranking and Compare work without the model. If
        it cannot be reached, or the daily allowance is used up, the sentence
        box and the Ask page say so, and everything else carries on.
      </p>

      <h2>Limits</h2>
      <p>
        The checks catch invented numbers and sources, but not every possible
        mistake: a model can still summarise a correct passage badly. Answers
        are information, not legal or visa advice. For anything that matters,
        open the linked official page.
      </p>
    </InfoPage>
  );
}

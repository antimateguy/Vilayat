import type { Metadata } from "next";
import Link from "next/link";

import { InfoPage } from "@/components/info/InfoPage";

export const metadata: Metadata = { title: "Privacy · Vilayat" };

export default function PrivacyPage() {
  return (
    <InfoPage
      kicker="Privacy"
      title="What happens to your data"
      intro="Vilayat has no accounts, sets no cookies and runs no analytics or advertising. You can use all of it without telling it who you are."
    >
      <h2>What stays in your browser</h2>
      <p>
        Your settings (city, campus, rent ceiling, travel limit, weights) are
        kept in the page address, so you can bookmark or share a search. They
        are not stored anywhere else. Nothing is written to your browser&apos;s
        storage and no cookies are set.
      </p>

      <h2>What the server receives</h2>
      <ul>
        <li>
          <strong>Your searches</strong>: the settings above, to rank the areas.
          They contain nothing personal and are not stored.
        </li>
        <li>
          <strong>Sentences and questions</strong> you type into the planner or
          Ask. They are passed on to the language model (see below) and not
          stored by Vilayat.
        </li>
        <li>
          <strong>Your IP address</strong>, which every website receives. It is
          kept only in the server&apos;s working memory, to limit how many
          requests one address can send in a minute, and is gone when the server
          restarts. It is not written to Vilayat&apos;s logs or to disk.
        </li>
      </ul>
      <p>
        The server keeps a technical log of each request: the time, the address
        on the site that was called, the result and how long it took. It does
        not contain your IP address or what you typed. Wherever the site is
        hosted, the hosting provider may keep its own access logs under its own
        privacy policy.
      </p>

      <h2>The language model</h2>
      <p>
        Sentences typed into the planner and questions asked on Ask are sent to
        Google&apos;s Gemini API to be understood and answered. Vilayat uses
        Gemini&apos;s free tier. Under the{" "}
        <a href="https://ai.google.dev/gemini-api/terms">Gemini API terms</a>,
        Google may use what is sent on the free tier to improve its products,
        and people at Google may read it.{" "}
        <strong>
          Do not type your name, passport number, address or anything else
          personal into these boxes.
        </strong>{" "}
        Questions about your situation work just as well without them.
      </p>
      <p>
        Everything else (the planner, the map, Compare) works without sending
        anything to Google. How the model is used is explained on{" "}
        <Link href="/ai">How we use AI</Link>.
      </p>

      <h2>Other services your browser contacts</h2>
      <ul>
        <li>
          <strong>OpenFreeMap</strong> supplies the map tiles, so your browser
          requests them from OpenFreeMap&apos;s servers, which see your IP
          address.
        </li>
        <li>
          <strong>Listing portals</strong> open only when you follow one of the
          links to them; from then on their own privacy policies apply.
        </li>
      </ul>
      <p>
        The font and the photographs are served by Vilayat itself, so loading a
        page does not contact Google Fonts or Wikimedia.
      </p>

      <h2>Questions</h2>
      <p>
        Because Vilayat stores nothing that identifies you, there is no personal
        data to look up, correct or delete. For anything else, see{" "}
        <Link href="/contact">Contact</Link>.
      </p>
    </InfoPage>
  );
}

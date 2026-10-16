import type { Metadata } from "next";
import Link from "next/link";

import { InfoPage } from "@/components/info/InfoPage";

export const metadata: Metadata = { title: "How it works · Vilayat" };

export default function AboutPage() {
  return (
    <InfoPage
      kicker="About"
      title="How Vilayat works"
      intro="Vilayat helps students moving from India to Berlin or Munich decide which neighbourhoods to search in before they look at a single flat."
    >
      <h2>What it does</h2>
      <p>
        You pick a university campus, the most you can pay in rent and the
        longest you are willing to travel each morning. Vilayat then ranks the
        city&apos;s neighbourhoods by how well they fit, shows them on a map and
        explains each position in plain words.
      </p>
      <p>
        It ranks <strong>areas, not flats</strong>. When you have chosen a few
        areas, it links you to the usual listing portals so you can search
        there. Vilayat does not copy listings from those portals and does not
        show vacancies.
      </p>

      <h2>The three views</h2>
      <ul>
        <li>
          <Link href="/planner">Planner</Link>: the map and the ranked list. You
          can also type what you want as a sentence, for example &ldquo;near
          TUM, under 800 euros, quiet&rdquo;, and it fills in the settings for
          you.
        </li>
        <li>
          <Link href="/compare">Compare</Link>: the same budget at every
          university in the city, to see where it goes furthest.
        </li>
        <li>
          <Link href="/ask">Ask</Link>: questions about registration, the
          residence permit, health insurance, working while studying and similar
          paperwork, answered from a set of stored documents with the source
          named.
        </li>
      </ul>

      <h2>How the ranking is worked out</h2>
      <p>
        First, areas that break one of your hard limits are set aside: rent
        above your ceiling or a typical commute longer than your limit. They are
        still listed, with the reason they were excluded.
      </p>
      <p>
        The remaining areas get a score between 0 and 1 for each of four things,
        and a weighted average decides the order:
      </p>
      <ul>
        <li>
          <strong>Commute</strong> (35% by default): 1 on the doorstep of the
          campus, 0 at your own limit.
        </li>
        <li>
          <strong>Rent</strong> (35%): 0 at your ceiling, 1 at half of it or
          less.
        </li>
        <li>
          <strong>Everyday amenities</strong> (15%): supermarkets, cafés,
          libraries, gyms and similar places per square kilometre.
        </li>
        <li>
          <strong>Part-time job access</strong> (15%): how many places that
          typically hire students are within reach. This shows where such
          employers cluster; it is not a count of open jobs.
        </li>
      </ul>
      <p>
        You can move the weights yourself, or mark a priority as important,
        which raises its weight above all the defaults. Every reason shown next
        to an area is written by the same code that scored it, so the
        explanation always matches the number.
      </p>

      <h2>How commute times are measured</h2>
      <p>
        The city is divided into small hexagons, about 0.7 km² each. For every
        hexagon, the travel time to each campus is computed by public transport
        and walking, using the transport operator&apos;s published timetable and
        OpenStreetMap footpaths, at walking speed 4.8 km/h. The trip is tried
        for every departure minute between 07:30 and 09:00, and the middle value
        (the median) is kept, so one lucky or unlucky connection does not decide
        the figure.
      </p>
      <p>
        An area&apos;s commute is the median over its hexagons. The commute
        layer on the planner map shows the hexagons themselves, because the far
        edge of a large district can be much further from the campus than its
        centre. Two neighbouring areas can therefore show the same figure, or
        quite different ones if a fast line runs through only one of them.
      </p>
      <p>
        When you open an area, the planner also shows one typical trip step by
        step (walk to the stop, which line, where to change, walk to campus) and
        draws it on the map. It starts from the hexagon whose time is closest to
        the area&apos;s median, and of the trips leaving between 07:30 and 09:00
        it is the one whose length is closest to that hexagon&apos;s typical
        time. It shows how the trip goes, not the fastest possible connection.
      </p>
      <p>
        All of this is computed in advance, so searches answer straight away.
        Where Vilayat has no figure for something, it says &ldquo;unknown&rdquo;
        rather than guessing.
      </p>

      <h2>Where the data comes from</h2>
      <p>
        Each dataset, its publisher, licence and date are listed on{" "}
        <Link href="/data">Data and sources</Link>, which also explains the
        figures marked with an asterisk. How the language model is used, and
        what it is not allowed to decide, is on{" "}
        <Link href="/ai">How we use AI</Link>.
      </p>

      <h2>Who made it</h2>
      <p>
        Vilayat is a student project, built as a B.Tech minor project on
        generative AI and cloud computing (project name EduCommute Matrix). It
        is not run by a university, a city or a housing company.
      </p>
    </InfoPage>
  );
}

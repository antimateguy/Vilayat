import type { Metadata } from "next";
import Link from "next/link";

import { InfoPage } from "@/components/info/InfoPage";
import { LiveSources } from "@/components/info/LiveSources";
import { UNIVERSITY_PHOTOS } from "@/lib/universities";

export const metadata: Metadata = { title: "Data and sources · Vilayat" };

export default function DataPage() {
  return (
    <InfoPage
      kicker="Data and sources"
      title="Where the figures come from"
      intro="Every figure in Vilayat comes from a named dataset with a date. Where there is no figure, the app says “unknown” instead of guessing."
    >
      <h2 id="placeholder">What the asterisk means</h2>
      <p>
        A figure or item marked with an asterisk (*) is{" "}
        <strong>placeholder data</strong>. It is there so the app can be built,
        tested and shown, and will be replaced when real data is available.
        Treat anything marked this way as an illustration of the method, not as
        a fact about the place.
      </p>
      <h3>Rents</h3>
      <p>
        No real rent dataset has been loaded yet. The rent shown for each area
        is a made-up figure in a plausible range, so the ranking, the map and
        the comparisons can be demonstrated. Because rent counts for a large
        part of each score, the order of the areas is an illustration too.
        Commute times, amenities and job access are real data (see below).
      </p>
      <p>
        For real asking rents, use the listing portals linked from each area, or
        a published rent index such as a city&apos;s Mietspiegel.
      </p>
      <h3>The list of employers</h3>
      <p>
        The large employers you can choose as a part-time job destination are a
        proposed list that has not been confirmed with the companies. Their
        locations are real addresses, but whether they hire students, and where,
        has not been checked.
      </p>
      <h3>The documents behind Ask</h3>
      <p>
        The answers on the Ask page come from short notes written for this
        project. Each note summarises one official page, which is linked beside
        the answer, as it read on the date shown. The notes are not the official
        wording, have not been checked by the publishers and will go out of
        date. Before any visa, permit or contract decision, follow the link and
        read the official page.
      </p>

      <h2>Datasets in use</h2>
      <p>
        This list is read live from the server, with each publisher&apos;s
        licence and the date the data was downloaded.
      </p>
      <LiveSources />

      <h2>How the figures are made</h2>
      <ul>
        <li>
          <strong>Commute times</strong> are computed in advance from the
          transport operator&apos;s timetable (GTFS) and OpenStreetMap
          footpaths, by public transport and walking, for every departure minute
          from 07:30 to 09:00; the median is kept. The details are on{" "}
          <Link href="/about">How it works</Link>.
        </li>
        <li>
          <strong>Amenities and job access</strong> count places mapped in
          OpenStreetMap: supermarkets, cafés, libraries and gyms for amenities;
          cafés, restaurants, bars, shops and supermarkets for job access.
          OpenStreetMap is edited by volunteers, so some places are missing and
          some have closed.
        </li>
        <li>
          <strong>Area boundaries</strong> are the official districts published
          by each city.
        </li>
      </ul>

      <h2>Map and photographs</h2>
      <p>
        Base map ©{" "}
        <a href="https://www.openstreetmap.org/copyright">
          OpenStreetMap contributors
        </a>
        , served by <a href="https://openfreemap.org/">OpenFreeMap</a>.
      </p>
      <p>
        University photographs are from Wikimedia Commons, used under their
        licences:
      </p>
      <ul>
        {Object.entries(UNIVERSITY_PHOTOS).map(([name, photo]) => (
          <li key={name}>
            {name}: <a href={photo.source}>{photo.credit}</a>
          </li>
        ))}
      </ul>

      <h2>Found a mistake?</h2>
      <p>
        If a figure looks wrong, see <Link href="/contact">Contact</Link>.
      </p>
    </InfoPage>
  );
}

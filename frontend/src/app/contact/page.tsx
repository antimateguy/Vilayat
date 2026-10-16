import type { Metadata } from "next";
import Link from "next/link";

import { InfoPage } from "@/components/info/InfoPage";

export const metadata: Metadata = { title: "Contact · Vilayat" };

// Set when the site is built (NEXT_PUBLIC_CONTACT_EMAIL). Left empty, no
// address is published.
const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim() ?? "";

export default function ContactPage() {
  return (
    <InfoPage
      kicker="Contact"
      title="Get in touch"
      intro="Vilayat is a non-commercial student project, made as a B.Tech minor project (EduCommute Matrix). It is not connected to any university, city authority or housing company."
    >
      <h2>Reporting a mistake</h2>
      {CONTACT_EMAIL ? (
        <p>
          If a figure, a travel time or an answer looks wrong, write to{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. Say which
          page, area or question it was, and what you expected.
        </p>
      ) : (
        <p>
          No contact address has been published for this copy of the site.
          Mistakes can be reported to the people running it through the channel
          where you found the link.
        </p>
      )}
      <p>
        Please do not send personal documents or details of your visa case.
        Vilayat cannot advise on individual cases; your university&apos;s
        international office can.
      </p>

      <h2>Questions about your data</h2>
      <p>
        Vilayat stores nothing that identifies you; the details are on{" "}
        <Link href="/privacy">Privacy</Link>.
      </p>

      <h2>Legal notice</h2>
      <p>
        This is a study project that is not run as a business. If it is operated
        as a public service in Germany, the operator&apos;s name and postal
        address will be given here as a legal notice (Impressum).
      </p>
    </InfoPage>
  );
}

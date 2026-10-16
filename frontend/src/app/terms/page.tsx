import type { Metadata } from "next";
import Link from "next/link";

import { InfoPage } from "@/components/info/InfoPage";

export const metadata: Metadata = { title: "Terms of use · Vilayat" };

export default function TermsPage() {
  return (
    <InfoPage
      kicker="Terms of use"
      title="Using Vilayat"
      intro="Vilayat is a free student project that helps you narrow down where to look for a home. By using it you accept the points below."
    >
      <h2>Information, not advice</h2>
      <p>
        Nothing on Vilayat is legal, immigration, tax or financial advice. Visa
        and residence rules, fees and deadlines change, and your own situation
        may differ from the general case. Check anything you rely on with the
        official body named in the source, your university&apos;s international
        office or a qualified adviser.
      </p>

      <h2>No guarantee of accuracy</h2>
      <p>
        The rankings, travel times and answers are worked out from the data
        listed on <Link href="/data">Data and sources</Link>. That data can be
        incomplete or out of date, and figures marked with an asterisk are
        placeholders. Travel times are typical values from the published
        timetable, not a promise of how long a particular journey will take.
        Vilayat is provided as it is, without any warranty, and the people who
        made it are not liable for decisions taken on the basis of it, as far as
        the law allows.
      </p>

      <h2>Answers written by a language model</h2>
      <p>
        Some text is written by a language model and checked automatically
        before it is shown (see <Link href="/ai">How we use AI</Link>). The
        checks reduce mistakes but cannot rule them out. The linked source is
        what counts.
      </p>

      <h2>Links to other sites</h2>
      <p>
        Vilayat links to listing portals, public authorities and other sites it
        does not control. It is not responsible for their content, their
        listings or their terms, and links are not an endorsement. Never pay a
        deposit or rent for a flat you have not seen or a landlord you cannot
        verify.
      </p>

      <h2>Fair use</h2>
      <p>
        Please do not send automated requests in bulk or try to get around the
        request limits. They keep the free service available for everyone.
      </p>

      <h2>Content and licences</h2>
      <p>
        The underlying datasets and photographs belong to their publishers and
        are used under the licences named on{" "}
        <Link href="/data">Data and sources</Link>. If you reuse them, those
        licences apply to you too.
      </p>

      <h2>Changes</h2>
      <p>
        These terms may be updated as the project develops; the date below shows
        the latest version.
      </p>
    </InfoPage>
  );
}

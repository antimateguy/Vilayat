import type { Metadata } from "next";
import { Suspense } from "react";

import { AskView } from "@/components/ask/AskView";

export const metadata: Metadata = { title: "Ask · Vilayat" };

export default function AskPage() {
  // The view reads the page address, which a static export needs a boundary for.
  return (
    <Suspense>
      <AskView />
    </Suspense>
  );
}

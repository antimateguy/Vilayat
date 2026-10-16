import type { Metadata } from "next";
import { Suspense } from "react";

import { ComparisonView } from "@/components/compare/ComparisonView";

export const metadata: Metadata = {
  title: "Compare · Vilayat",
};

export default function ComparePage() {
  return (
    <Suspense fallback={<p className="text-ink-2 p-4 text-sm">Loading…</p>}>
      <ComparisonView />
    </Suspense>
  );
}

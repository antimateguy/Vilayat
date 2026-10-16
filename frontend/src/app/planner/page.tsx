import type { Metadata } from "next";
import { Suspense } from "react";

import { Planner } from "@/components/planner/Planner";

export const metadata: Metadata = { title: "Planner · Vilayat" };

export default function PlannerPage() {
  return (
    // The planner reads its settings from the page address, which only exists
    // in the browser; the fallback is what the pre-built HTML contains.
    <Suspense fallback={<p className="text-ink-2 p-4 text-sm">Loading…</p>}>
      <Planner />
    </Suspense>
  );
}

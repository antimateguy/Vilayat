"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "@/lib/api/client";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Retrying cannot fix a request the API rejected (4xx), and retrying a
        // rate-limited one makes it worse. Only a server or network failure is
        // tried once more.
        retry: (failures, error) =>
          failures < 1 &&
          error instanceof ApiError &&
          (error.status === 0 || error.status >= 500),
        refetchOnWindowFocus: false,
      },
    },
  });
}

export function Providers({ children }: { children: React.ReactNode }) {
  // Created once per browser session; useState keeps it across re-renders.
  const [queryClient] = useState(makeQueryClient);

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

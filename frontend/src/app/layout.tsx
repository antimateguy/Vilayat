import type { Metadata } from "next";
import { Source_Serif_4 } from "next/font/google";

import { Providers } from "./providers";
import "./globals.css";

// Downloaded at build time and served with the site: visitors' browsers never
// contact Google for it.
const sourceSerif = Source_Serif_4({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "600"],
  style: ["normal", "italic"],
  variable: "--font-source-serif",
});

export const metadata: Metadata = {
  title: "Vilayat · India to Germany student relocation",
  description:
    "Find Berlin and Munich neighbourhoods that fit your rent, your commute to campus and a part-time job, and get the paperwork answered from official documents.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sourceSerif.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

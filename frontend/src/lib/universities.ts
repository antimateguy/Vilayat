// Photographs of the universities, shown on the home page and the comparison.
// Every photo is from Wikimedia Commons under a free licence; the licences
// require the photographer to be named next to the photo, so each entry
// carries its credit and a link to the file's page.

export interface Photo {
  src: string;
  alt: string;
  /** "Photographer, licence", shown under the photo. */
  credit: string;
  source: string;
}

const COMMONS = "https://commons.wikimedia.org/wiki/File:";

/** Keyed by the university's short name, as the API sends it. */
export const UNIVERSITY_PHOTOS: Record<string, Photo> = {
  TUM: {
    src: "/universities/tum.jpg",
    alt: "Main building of the Technical University of Munich on Arcisstraße",
    credit: "Rufus46, CC BY-SA 3.0",
    source: `${COMMONS}Arcisstr._21_TUM_Muenchen-1.jpg`,
  },
  LMU: {
    src: "/universities/lmu.jpg",
    alt: "Geschwister-Scholl-Platz in front of the LMU main building in Munich",
    credit: "Felix Edelmann, CC0",
    source: `${COMMONS}Geschwister-Scholl-Platz_2021.jpg`,
  },
  HM: {
    src: "/universities/hm-muenchen.jpg",
    alt: "Hochschule München on Lothstraße",
    credit: "Johannes Vogel, CC BY-SA 3.0",
    source: `${COMMONS}Hochschule_Muenchen_Ansicht_Lothstrasse.jpg`,
  },
  "FU Berlin": {
    src: "/universities/fu-berlin.jpg",
    alt: "Henry-Ford-Bau of the Freie Universität Berlin in Dahlem",
    credit: "Gunnar Klack, CC BY-SA 4.0",
    source: `${COMMONS}Henry-Ford-Bau-Freie-Universitaet-Berlin-Dahlem-10-2018a.jpg`,
  },
  "HU Berlin": {
    src: "/universities/hu-berlin.jpg",
    alt: "Main building of the Humboldt-Universität on Unter den Linden",
    credit: "Christian Wolf, CC BY-SA 3.0 DE",
    source: `${COMMONS}Frontansicht_des_Hauptgebäudes_der_Humboldt-Universität_in_Berlin.jpg`,
  },
  "TU Berlin": {
    src: "/universities/tu-berlin.jpg",
    alt: "Main building of the Technische Universität Berlin in Charlottenburg",
    credit: "Gunnar Klack, CC BY-SA 4.0",
    source: `${COMMONS}Technische-Universitaet-Hauptgebaeude-Berlin-Charlottenburg-06-2017.jpg`,
  },
  "HTW Berlin": {
    src: "/universities/htw-berlin.jpg",
    alt: "HTW Berlin, Campus Wilhelminenhof in Oberschöneweide",
    credit: "Gunnar Klack, CC BY-SA 4.0",
    source: `${COMMONS}2024-10-20-HTW-Campus-Wilhelminenhofstr-Berlin-Oberschoeneweide.jpg`,
  },
};

/** The order the home page cycles through: alternating the two cities. */
export const HERO_ORDER = [
  "TUM",
  "HU Berlin",
  "LMU",
  "FU Berlin",
  "HM",
  "TU Berlin",
  "HTW Berlin",
] as const;

export function photoFor(shortName: string): Photo | null {
  return UNIVERSITY_PHOTOS[shortName] ?? null;
}

/** The index after `index`, wrapping round at the end. */
export function nextIndex(index: number, length: number): number {
  return length > 0 ? (index + 1) % length : 0;
}

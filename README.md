# Vilayat

**Find the Berlin or Munich neighbourhood that fits your rent, your commute and a part-time job.**

Vilayat (विलायत, "abroad") helps students moving from India to Germany decide
*where* to look for a home before they look at a single flat. Pick a
university campus, a rent ceiling and the longest commute you will accept, and
Vilayat ranks every district of the city, shows them on a map, explains each
position in plain words and links to the listing portals for the areas you
choose.

> Project name: EduCommute Matrix, a B.Tech minor project on generative AI and
> cloud computing.

## Features

- **Ranked neighbourhoods, not flats.** Every district of Berlin (97) and
  Munich (25) is scored on commute, rent, everyday amenities and access to
  part-time jobs; the weights are yours to change.
- **Real commute times.** Travel by public transport and on foot from every
  0.7 km² hexagon to every campus, computed from the transport operators'
  timetables for each minute of the morning rush hour.
- **The trip, step by step.** For each area and campus, one typical journey:
  walk to the stop, which line, where to change, drawn on the map in the
  lines' colours. With a job pinned, the afternoon leg from campus to work too.
- **A day with a job.** Pin an employer and see the whole day's travel: home,
  campus, work, home.
- **Ask about the paperwork.** Questions on registration, the residence permit,
  working while studying and the broadcasting fee are answered from stored
  official sources, with every statement citing its source.
- **Plain-language input.** Type "near TUM, under 800 euros, 30 minutes" and
  the controls are filled in for you.

## How the AI is used

A language model (Google Gemini) only translates and explains; it never decides
the ranking, which is ordinary code that gives the same answer every time.

| Where | What the model does | What the code checks |
| --- | --- | --- |
| Sentence search | Fills in a form from your sentence | Campuses and employers must exist; numbers must be in range |
| Ask | Answers from the closest stored passages | No close passage: no answer. Every answer must cite a passage, and every figure must appear in it |
| Area summaries | Writes two or three sentences per area, offline | Only the area's own figures and name may appear |

The free tier's daily allowance is a hard limit: every request is counted
before it is sent, and when the day's allowance is used up the AI features say
when they are back. Without an API key the AI features are off and everything
else works.

## Quick start

Requirements: [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
git clone https://github.com/antimateguy/Vilayat.git
cd Vilayat
docker compose up -d
```

Open <http://localhost:3000>. The first start builds the images (a few
minutes) and loads the prepared data from `db/seed/vilayat.dump`, so nothing
else needs to run. On Windows, double-click `start.bat` instead.

To switch on the AI features, copy `.env.example` to `.env`, add a key from
[Google AI Studio](https://aistudio.google.com/) as `GEMINI_API_KEY=...`, and
run `docker compose up -d` again. `.env` is ignored by Git.

| Address | What |
| --- | --- |
| <http://localhost:3000> | The website |
| <http://localhost:8000/docs> | The API, with interactive documentation |
| <http://localhost:8000/health> | API and database health |

## Architecture

```text
Browser ── static site (Next.js export) ──► FastAPI ──► PostgreSQL + PostGIS + pgvector
                                              │
                                              └──► Gemini API (optional)

Offline jobs (developer machine): timetables and OpenStreetMap ──► R5 routing,
places, documents, summaries ──► the same database ──► db/seed/vilayat.dump
```

The backend follows a ports-and-adapters (hexagonal) layout: `domain/` holds
plain Python concepts, `services/` the use cases, `ports/` the interfaces, and
`infrastructure/` their implementations (PostgreSQL, Gemini, files). Nothing
slow happens while a visitor waits: every travel time, journey and summary is
computed in advance.

| Layer | Technology |
| --- | --- |
| Frontend | Next.js 16 (static export), React 19, Tailwind CSS 4, TanStack Query, MapLibre GL |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Database | PostgreSQL 17, PostGIS, pgvector, H3 hexagons |
| Routing | R5 via r5py (offline, Java 21) |
| AI | Gemini (text and embeddings) through the `google-genai` SDK |
| Hosting | Cloudflare Pages, Render, Neon |

## Repository

```text
backend/    FastAPI app, offline jobs and tests (managed by uv)
frontend/   Next.js app, served as static files
db/         Database image, first-start scripts and the seed dump
docs/       Developer guide, data storage, deployment
```

- [Developer guide](docs/developer-guide.md): setup, running the offline jobs,
  tests, the API and the AI layer in detail.
- [Where the data lives](docs/data-storage.md): every file and table, and the
  job that writes it.
- [Deployment](docs/deployment.md): Cloudflare Pages, Render and Neon, step by
  step.

## Data and credits

| Data | Source | Licence |
| --- | --- | --- |
| District boundaries | Geoportal Berlin; Landeshauptstadt München | dl-de/zero-2.0; dl-de/by-2.0 |
| Timetables | VBB Verkehrsverbund Berlin-Brandenburg; Münchner Verkehrs- und Tarifverbund (MVV) | CC BY 4.0; CC BY |
| Streets, places, campus locations | © OpenStreetMap contributors | ODbL |
| Base map | OpenFreeMap (OpenStreetMap data) | ODbL |
| University photographs | Wikimedia Commons (credits in `frontend/public/universities/README.md`) | CC BY-SA, CC0 |
| Ask documents | German federal law (gesetze-im-internet.de), Berlin and Munich service pages, Minijob-Zentrale, Verbraucherzentrale | Laws: no copyright (§ 5 UrhG). Other pages are linked, not reproduced |

**Rents and the employer list are placeholders** until real data is supplied;
the site marks them with an asterisk and explains this on its *Data and
sources* page.

Vilayat is information, not legal or visa advice.

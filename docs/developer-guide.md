# Developer guide

How to set up, run, test and extend Vilayat. For an overview of what the app
does, start with the [README](../README.md).

- [Repository layout](#repository-layout)
- [Setup and running](#setup-and-running)
- [How a search is decided](#how-a-search-is-decided)
- [AI layer](#ai-layer)
- [Frontend](#frontend)
- [API](#api)
- [Data](#data)
- [Offline jobs](#offline-jobs)
- [Database migrations](#database-migrations)
- [Checks and continuous integration](#checks-and-continuous-integration)
- [Deployment](#deployment)

## Repository layout

```text
backend/            FastAPI app, offline jobs and tests (Python 3.12, managed by uv)
  api/              routes, request and response schemas, composition root
  domain/           core concepts as plain Python
  services/         use cases; they depend only on ports
  ports/            abstract interfaces
  infrastructure/   PostgreSQL, Gemini and file adapters; fakes for tests
  cities/           per-city configuration (universities, feeds, portals)
  jobs/             offline jobs that build the data the API reads
  evaluation/       measures for the AI layer
  data/             boundaries, places, sample data, document notes, labels
  tests/            unit/ (no database) and integration/ (Compose database)
frontend/           Next.js app, built as a static export (served by nginx in Docker)
db/                 Postgres 17 image with PostGIS and pgvector, seed dump and scripts
docs/               this guide
```

The backend follows a ports-and-adapters (hexagonal) layout. Dependencies point
inwards, `api` → `services` → `ports` ← `infrastructure`, and the domain uses
only the standard library. `backend/tests/unit/test_architecture.py` reads every
import and fails if a layer reaches where it should not.

## Setup and running

| Tool                              | Version used      | Needed for                                        |
| --------------------------------- | ----------------- | ------------------------------------------------- |
| Docker Desktop (WSL 2 on Windows) | 29.8, Compose 5.5 | the whole stack                                   |
| uv                                | 0.12              | backend development (installs Python 3.12 itself) |
| Node.js and pnpm                  | 24 and 12         | frontend development                              |
| Java                              | 21                | the routing jobs only                             |

### Run everything in Docker

```bash
docker compose up -d
```

| Address                        | What                          |
| ------------------------------ | ----------------------------- |
| <http://localhost:3000>        | The website                   |
| <http://localhost:8000/docs>   | Interactive API documentation |
| <http://localhost:8000/health> | API and database health       |

The first start builds the images and loads `db/seed/vilayat.dump` into the new
database volume, so the site works at once. The API applies any pending
migrations whenever it starts. On Windows, `start.bat` does the same with a
double-click and opens the site.

Copy `.env.example` to `.env` to change ports, credentials or to add a Gemini
API key (`GEMINI_API_KEY=...`). `.env` is ignored by Git; never commit it.

After changing code, rebuild the part you changed:

```bash
docker compose up -d --build backend
```

```bash
docker compose up -d --build frontend
```

Stop everything and keep the data with `docker compose down`; add `-v` to delete
the database volume (the next start loads the seed again).

### Frontend with live reload

```bash
docker compose stop frontend
cd frontend && pnpm install && pnpm dev
```

If a terminal says `'pnpm' is not recognized`, run `npm run dev` instead, or add
pnpm's folder to that terminal's PATH (`$env:Path += ";$env:APPDATA\npm"` in
PowerShell).

### Backend with auto-reload

```bash
docker compose up -d db
docker compose stop backend
cd backend && uv sync && uv run uvicorn api.main:app --reload
```

## How a search is decided

Everything here is deterministic code in `backend/services/` and
`backend/domain/`; no language model takes part.

1. **Facts.** For each area: rent, morning commute to the chosen campus,
   everyday amenities and job access. A figure that is not known stays UNKNOWN.
2. **Hard limits.** Maximum commute and maximum rent are small specification
   objects combined with "and". Each area meets the limits, breaks one (with
   the reason) or cannot be checked because a figure is missing.
3. **Ranking.** Four scorers rate each matching area from 0 to 1: commute, rent,
   amenities and job access, weighted 35, 35, 15 and 15 by default. A scorer
   whose figure is unknown is left out and the others are scaled up.
4. **Explanation.** Every result lists one sentence per scorer and names its
   weakest point as the trade-off.
5. **Employer pin (optional).** With an employer pinned, each result also shows
   the day's travel (home, campus, job, home). This informs only; it never
   excludes an area or changes the order.

The comparison view counts, for one rent and commute limit, how many areas fit
around each campus, using the same limit objects.

### Commute times and journeys

Each area is split into H3 hexagons (resolution 8, about 0.7 km²). For every
hexagon and destination the routing engine R5 computes the door-to-door time by
public transport and on foot (walking at 4.8 km/h), for every departure minute
from 07:30 to 09:00 (and 17:00 to 19:00 for the way back), and keeps the median.
An area's commute is the median over its hexagons.

For the step-by-step view, one typical morning journey per area and campus is
planned with the same engine. It starts from the hexagon whose time is closest
to the area's median and keeps the departure whose length is closest to that
hexagon's median, so it shows a typical trip rather than the best case. With an
employer pinned, an afternoon journey from campus to the employer is added.

## AI layer

The engine decides; a language model only translates and explains. It is used
in three places, behind the `LLMClient` and `Embedder` ports
(`backend/ports/`), with Gemini as the implementation
(`backend/infrastructure/gemini/`).

| Feature                                 | What the model does                                         | What code checks afterwards                                                                                                                                                                              |
| --------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sentence search (`services/intent.py`)  | Fills in a fixed form from a sentence                       | Ids must exist in the catalogue, numbers must be in range; the normal search then runs                                                                                                                   |
| Ask (`services/rag.py`)                 | Writes an answer from the closest stored passages           | No passage similar enough: a fixed "no evidence" answer and no model call. An answer must cite passages, and every figure in it must appear in a passage it cites; otherwise only the passages are shown |
| Area summaries (`services/briefing.py`) | Puts an area's figures into two or three sentences, offline | The text must name the area exactly and contain no figure or name that was not in its input; it is shown only while those figures are current                                                            |

**Without a key**, a stand-in that is always "unavailable" replaces the Gemini
client (`infrastructure/ai_disabled.py`). `POST /intent` and `POST /ask` answer
503 with the code `ai_unavailable`, the frontend hides the sentence box and the
Ask page, and everything else works.

**A fixed daily allowance.** Every request, from the API or a job, is counted
in the `ai_usage` table before it is sent (`infrastructure/budget.py`); every
text in an embedding call counts as one request, as Google counts it. At the
limit nothing more is sent until Google's next day starts at midnight Pacific
time (`domain/quota.py`). `/ai/status` then reports `daily_limit_reached` and
`resets_at`, the two endpoints answer 503 with `ai_daily_limit` and
`Retry-After`, and the frontend says when the features are back. The SDK never
retries on its own, because every attempt counts.

| Setting                         | Default                 | Meaning                                                 |
| ------------------------------- | ----------------------- | ------------------------------------------------------- |
| `GEMINI_TEXT_MODEL`             | `gemini-3.5-flash-lite` | Text model                                              |
| `GEMINI_EMBEDDING_MODEL`        | `gemini-embedding-2`    | Embedding model (768 dimensions)                        |
| `AI_DAILY_TEXT_REQUESTS`        | 500                     | Text requests per day                                   |
| `AI_DAILY_EMBEDDING_REQUESTS`   | 1000                    | Embedded texts per day                                  |
| `AI_EMBEDDING_TEXTS_PER_MINUTE` | 90                      | Pace of offline embedding jobs                          |
| `AI_RATE_LIMIT_PER_MINUTE`      | 10                      | Requests per visitor per minute to the two AI endpoints |
| `RAG_MIN_SIMILARITY`            | 0.68                    | Lowest similarity at which a passage counts as evidence |

Requests on Google's free tier may be used by Google to improve its products, so
the app sends only the sentence or question a visitor typed and public figures.

### The document library

Ask answers from two kinds of documents:

- **Notes** in `backend/data/documents/*.md`: short summaries written for this
  project, each linked to the official page it summarises. They are marked as
  summaries on the site.
- **Official pages** listed in `backend/data/documents/sources.json` (sections of
  the Residence Act and the Federal Registration Act, Berlin and Munich service
  pages, the Minijob-Zentrale and the Verbraucherzentrale).
  `jobs.fetch_documents` reads them offline as an identified program that
  follows robots.txt, skips pages that reserve text and data mining and waits
  two seconds between pages. The fetched text is not committed. It is shown
  word for word only where that is allowed (the laws, which carry no
  copyright); for the other pages the site gives the answer and a link.

### Evaluation

`backend/evaluation/` measures the AI layer on the labelled questions and
sentences in `backend/data/evaluation/`: which embedding model ranks the right
section first, how well the similarity threshold separates covered from
uncovered questions, how many questions are answered with a correct source, and
how accurately a sentence becomes search settings. The labels are few and were
written for this project, so the figures show that the pipeline works rather
than predict accuracy on real questions.

## Frontend

All pages are in `frontend/src/app/`; the site is exported as static files.

- **Home** (`/`): what the app does, photographs of the universities, a planner
  card with a live count of fitting areas, and a question card.
- **Planner** (`/planner`): city, campus, rent ceiling, commute limit, optional
  employer and priorities, or a typed sentence. The map shows the ranking or a
  hexagon layer (commute, amenities, jobs). Choosing an area opens its details;
  on the Commute layer the map then shows the area and its typical trip, drawn
  in the lines' colours. Universities, employers and the U-Bahn, S-Bahn and tram
  lines can be shown on any layer. The map frames what matters automatically,
  clear of the side panes, which can be folded away.
- **Compare** (`/compare`): how many areas fit one budget around each campus.
- **Ask** (`/ask`): questions about moving, answered with numbered sources.
  `/ask?city=munich&q=...` asks a question on arrival.
- **Information pages**: `/about`, `/data`, `/ai`, `/privacy`, `/terms` and
  `/contact`, linked from the footer. Placeholder figures carry an asterisk that
  links to `/data#placeholder`.

| Folder                                              | Contents                                                                                 |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `src/lib/api/`                                      | Zod schemas and query hooks for every endpoint, with fixtures captured from the real API |
| `src/lib/`                                          | Pure logic: address-bar state, formatting, map colours and framing, journeys, citations  |
| `src/components/planner/`                           | Sentence box, controls, results, map, area details                                       |
| `src/components/home/`, `compare/`, `ask/`, `info/` | The other pages                                                                          |

The base map comes from OpenFreeMap (no key needed). The university photographs
are from Wikimedia Commons; each is shown with its credit (see
`frontend/public/universities/README.md`). Build-time settings:
`NEXT_PUBLIC_API_BASE_URL` (the API's address) and, optionally,
`NEXT_PUBLIC_CONTACT_EMAIL` (shown on the Contact page).

## API

Interactive documentation with every endpoint, schema and example is at `/docs`
on a running API. Product endpoints live under `/api/v1`.

| Endpoint                                                           | Purpose                                                                      |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| `GET /cities`                                                      | Cities covered                                                               |
| `GET /cities/{city}/universities`                                  | Universities with their campuses                                             |
| `GET /cities/{city}/employers`                                     | Employer sites that can be pinned                                            |
| `GET /cities/{city}/sources`                                       | Publisher, licence and date of every dataset                                 |
| `POST /search`                                                     | Rank the areas for a campus, rent ceiling and commute limit                  |
| `GET /areas/{id}?campus_id=`                                       | One area in detail, with links to rental portals                             |
| `GET /areas/{id}/commute?campus_id=&employer_id=`                  | The spread of commute times and the typical journey (and campus to employer) |
| `GET /areas/{id}/briefing`                                         | The stored area summary; never calls a model                                 |
| `GET /cities/{city}/comparison?max_rent_eur=&max_commute_minutes=` | Fitting areas per university                                                 |
| `GET /cities/{city}/layers/areas`                                  | Area outlines as GeoJSON                                                     |
| `GET /cities/{city}/layers/cells?metric=&campus_id=`               | Hexagon layer as GeoJSON (`commute`, `amenities`, `job_access`)              |
| `GET /cities/{city}/layers/transit`                                | U-Bahn, S-Bahn and tram lines as GeoJSON                                     |
| `GET /ai/status`                                                   | Whether a model is configured and whether today's allowance is spent         |
| `POST /intent`                                                     | Turn a sentence into search settings                                         |
| `POST /ask`                                                        | Answer a question from the stored documents, with citations                  |
| `GET /health`, `GET /health/live`                                  | Health with the database check; liveness without it                          |

Conventions:

- A figure that is not known is the string `"UNKNOWN"`, never `null` or a guess.
- Every error has the shape `{"error": {"code", "message", "request_id", "details"}}`.
- Every response carries `X-Request-ID` and a `Server-Timing` header.
- One visitor may make 120 requests a minute (`RATE_LIMIT_PER_MINUTE`); beyond
  that the answer is 429 with `Retry-After`.

```bash
curl -s -X POST http://localhost:8000/api/v1/search -H "Content-Type: application/json" -d '{"campus_id": 8, "max_commute_minutes": 35, "max_rent_eur": 800}'
```

## Data

| Data                     | Source                                           | Licence                      | Status               |
| ------------------------ | ------------------------------------------------ | ---------------------------- | -------------------- |
| District boundaries      | Geoportal Berlin; Landeshauptstadt München       | dl-de/zero-2.0; dl-de/by-2.0 | Official             |
| Campus locations, places | OpenStreetMap (Nominatim, Overpass)              | ODbL                         | Real                 |
| Timetables               | VBB; MVV                                         | CC BY 4.0; CC BY             | Real                 |
| Street networks          | OpenStreetMap (extracts by Geofabrik and BBBike) | ODbL                         | Real                 |
| Area rents               | `backend/data/rents/sample_rents.csv`            | none                         | **Placeholder**      |
| Employer sites           | `backend/data/employers/sample_employers.csv`    | coordinates: ODbL            | **Placeholder list** |
| Ask documents            | Notes and official pages (see above)             | see above                    | Notes are summaries  |

Each folder under [`backend/data/`](../backend/data/) has a README with its
source and file format: [boundaries](../backend/data/boundaries/README.md),
[osm](../backend/data/osm/README.md), [rents](../backend/data/rents/README.md),
[employers](../backend/data/employers/README.md),
[documents](../backend/data/documents/README.md) and
[evaluation](../backend/data/evaluation/README.md). Cities are configured in
`backend/cities/`; adding a city means adding one module there and running the
jobs below.

`db/seed/vilayat.dump` holds the whole prepared database (3.5 MB), apart from
the fetched official text and the usage counts. A new local database loads it on
its first start. After changing data, make a new one with `db/make-seed.sh`.

## Offline jobs

Everything slow is computed in advance by the jobs in `backend/jobs/`; the API
only reads the results. Run them from `backend/` with the database up. The seed
already contains their results, so they are needed only to change the data.

| Command                                                                    | What it does                                                                                        |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `uv run python -m jobs.load_base_data`                                     | Cities, campuses, boundaries, hexagons, places, job access, sample rents and employers (about 20 s) |
| `uv run python -m jobs.check_city_data`                                    | Summary of what was loaded                                                                          |
| `uv run python -m jobs.fetch_osm_places --city berlin`                     | Refresh a city's OpenStreetMap places                                                               |
| `uv run python -m jobs.fetch_feeds --city munich`                          | Download the timetable and street network (about 160 to 190 MB)                                     |
| `uv run --group routing python -m jobs.build_travel_times --city munich`   | Travel times; Munich about 4 minutes, Berlin about 20 (`--part 1/3` splits a run)                   |
| `uv run python -m jobs.check_travel_times`                                 | Spot-check travel times against known journeys                                                      |
| `uv run --group routing python -m jobs.build_commute_routes --city munich` | Typical journeys, about 8 s each; a stopped run carries on                                          |
| `uv run python -m jobs.build_transit_lines --city munich`                  | The line map (`backend/data/transit/<city>.geojson`)                                                |
| `uv run python -m jobs.fetch_documents`                                    | Fetch the official pages on the allow-list                                                          |
| `uv run python -m jobs.ingest_documents`                                   | Embed the notes and fetched pages for Ask (uses the embedding model)                                |
| `uv run python -m jobs.build_briefings --city munich`                      | Write area summaries whose figures changed (uses the text model)                                    |
| `uv run python -m jobs.check_ai`                                           | One small call to each configured model                                                             |

The routing jobs need Java 21; `--group routing` installs their Python packages.
Before routing, each timetable is trimmed to the city plus about 10 km
(`jobs/gtfs_prepare.py`) so that it fits in a laptop's memory.

## Database migrations

The schema is defined in `backend/infrastructure/db/models.py` and changed only
through Alembic migrations in `backend/migrations/versions/`. From `backend/`:

| Command                                               | What it does                               |
| ----------------------------------------------------- | ------------------------------------------ |
| `uv run alembic upgrade head`                         | Apply every migration not yet applied      |
| `uv run alembic current`                              | Show which migration the database is at    |
| `uv run alembic check`                                | Fail if the models and the database differ |
| `uv run alembic revision --autogenerate -m "message"` | Draft a migration from model changes       |

## Checks and continuous integration

Backend, from `backend/`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

- Unit tests only (no database): `uv run pytest -m "not integration"`.
- Integration tests need `docker compose up -d db`; they use their own database,
  `educommute_test`, rebuilt from the migrations on every run.
- The tests never call a real model: the AI services are tested with scripted
  fakes.

Frontend, from `frontend/`:

```bash
pnpm lint && pnpm typecheck && pnpm format:check && pnpm test && pnpm build
```

The schema tests parse responses captured from the real backend, so they fail if
the two drift apart. `pnpm build` writes the static site to `frontend/out/`.

GitHub Actions (`.github/workflows/ci.yml`) runs all of these on every push and
pull request, including the integration tests against the Compose database.

## Deployment

The live site runs on three free plans:

| Part     | Service                                        | Configuration                                                                                                                                                                                                                            |
| -------- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Website  | Cloudflare Pages                               | Root `frontend`; build `npx --yes pnpm@12.9.1 install --frozen-lockfile && npx --yes pnpm@12.9.1 run build`; output `out`; `NODE_VERSION=24` and `NEXT_PUBLIC_API_BASE_URL` (the API's address); `frontend/public/_headers` sets caching |
| API      | Render (Docker)                                | `render.yaml`; `DATABASE_URL`, `GEMINI_API_KEY` and `CORS_ORIGINS` (the website's address) are set in Render's dashboard, never in the repository                                                                                        |
| Database | Neon (PostgreSQL 17 with PostGIS and pgvector) | Filled once from the seed: put the address in `.env` as `PRODUCTION_DATABASE_URL` and run `docker run --rm --env-file .env -v ./db:/db:ro educommute-db:17 sh /db/load-seed.sh`                                                          |

The API applies migrations when it starts and is deployed by Render only after
the GitHub Actions checks pass. Render's free plan sleeps after 15 idle minutes;
`.github/workflows/keep-warm.yml` pings `/health/live` every 14 minutes during
the day when the repository variable `API_URL` is set.

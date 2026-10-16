# Developer guide

How to set up, run, test and extend Vilayat (project name: EduCommute Matrix).
For an overview see the [README](../README.md); for where every kind of data
lives see [data-storage.md](data-storage.md); for hosting see
[deployment.md](deployment.md).

## Repository layout

```text
backend/    FastAPI app and offline jobs (Python 3.12, managed by uv)
  api/             routes, request/response schemas, composition root
  domain/          core concepts as plain Python
  services/        use cases; depend only on ports
  ports/           abstract interfaces
  infrastructure/  database, external APIs, fakes for tests
  cities/          per-city configuration and registry
  jobs/            offline jobs that build the data the API reads
  evaluation/      measures for the AI layer (retrieval, threshold, answers, sentences)
  data/            boundaries, places, sample rents, sample documents, labelled questions
  tests/           unit/ (no database) and integration/ (Compose database)
frontend/   Next.js app, built as a static export; its Dockerfile serves that export with nginx
db/         Postgres 17 image with PostGIS and pgvector
docs/       developer guide, data storage, deployment
```

## Prerequisites

| Tool | Version used | Needed for |
| --- | --- | --- |
| Docker Desktop (WSL 2 on Windows) | 29.8, Compose 5.5 | database and backend containers |
| uv | 0.12 | Python 3.12 and backend dependencies |
| Node.js | 24 | frontend |
| pnpm | 12 | frontend dependencies |
| Java | 21 | travel-time job only (see "Travel times") |

uv installs Python 3.12 itself; no separate Python install is needed.

## First-time setup

```bash
cd backend && uv sync
```

```bash
cd frontend && pnpm install
```

Optional: copy `.env.example` to `.env` to change ports or credentials. The
stack starts with the built-in development defaults without it.

For the AI features, put a Gemini API key from Google AI Studio into `.env` as
`GEMINI_API_KEY=...`. Without a key those features are switched off and
everything else works (see "AI layer"). `.env` is git-ignored; never commit it.

## Run

Everything runs in Docker: the database, the backend and the frontend. From the
repository root:

```bash
docker compose up -d
```

- Site: <http://localhost:3000> (home page; the planner is at `/planner`)
- API health: <http://localhost:8000/health>
- API docs (OpenAPI): <http://localhost:8000/docs>

The first start builds the images, which takes a few minutes, and loads the
prepared data from `db/seed/vilayat.dump` into the new database volume, so the
site works at once without running any offline job. On Windows,
`start.bat` in the repository root does the same with a double-click: it starts
Docker Desktop if needed, runs the command above and opens the site.

The containers run the code as it was when their image was built. After
changing code, rebuild the part you changed:

```bash
docker compose up -d --build backend
```

```bash
docker compose up -d --build frontend
```

### Frontend with live reload

While editing frontend code it is quicker to run it on the host, where a saved
file shows up in the browser at once. Stop the frontend container first, since
both use port 3000:

```bash
docker compose stop frontend
```

```bash
cd frontend && pnpm dev
```

If the terminal says `'pnpm' is not recognized`, its PATH is missing the folder
pnpm was installed to. Either run `npm run dev` instead, which needs only
Node.js, or add the folder for that terminal first: `set PATH=%PATH%;%APPDATA%\npm`
in Command Prompt, `$env:Path += ";$env:APPDATA\npm"` in PowerShell.

Create or update the database tables (needed once after the first start, and
again whenever a new migration is added):

```bash
cd backend && uv run alembic upgrade head
```

Load the base data for both cities (cities, universities, campuses,
neighbourhood boundaries, H3 cells, OpenStreetMap places, job access, job
hotspots, sample rents and sample employers). Takes about 20 seconds and is safe
to run again:

```bash
cd backend && uv run python -m jobs.load_base_data
```

Check what was loaded; add `--city munich --list` for one line per area:

```bash
cd backend && uv run python -m jobs.check_city_data
```

With a Gemini key in `.env`, load the documents for question answering and
write the area briefings (about 40 and 130 model calls; both are safe to run
again and only redo what changed):

```bash
cd backend && uv run python -m jobs.ingest_documents
```

```bash
cd backend && uv run python -m jobs.build_briefings --city munich
```

Stop everything, keeping the data:

```bash
docker compose down
```

Stop and delete the database volume (the next start re-creates an empty database):

```bash
docker compose down -v
```

### Backend with auto-reload

While writing backend code it is quicker to run the API on the host against the
Compose database:

```bash
docker compose up -d db
```

```bash
cd backend && uv run uvicorn api.main:app --reload
```

Stop the `backend` container first (`docker compose stop backend`), since both
use port 8000.

## How a search is decided

Everything below is deterministic code in `backend/services/` and
`backend/domain/`; no language model takes part in it.

1. **Facts.** For each area of the city: rent, morning commute to the chosen
   campus, everyday amenities and job access. A figure that is not known stays
   UNKNOWN.
2. **Hard constraints.** Maximum commute, maximum rent and an optional minimum
   job access are small specification objects combined with "and". Each area
   ends up in one of three groups: it meets the limits, it breaks one (with the
   reason), or it cannot be checked because a figure is missing.
3. **Ranking.** Four scorers rate each matching area from 0 to 1: commute, rent,
   amenities and job access. The weights (default 35, 35, 15, 15) combine them. A
   scorer whose figure is unknown is left out and the others are scaled up.
4. **Explanation.** Every result lists one sentence per scorer, the most helpful
   first, and names its weakest point as the trade-off.
5. **Employer pin (optional).** With an employer pinned, each result also shows
   the day's travel for home, campus, job, home and how much the job adds. This
   informs only: it never excludes an area or changes the order.

The comparison view counts, for one rent and commute limit, how many areas are
feasible around each campus and university, using the same constraint objects.

## AI layer

The engine decides; a language model only translates and explains. It is used
in three places, each behind the `LLMClient` and `Embedder` ports
(`backend/ports/`), with Gemini as the implementation
(`backend/infrastructure/gemini/`).

| Feature | What the model does | What code checks afterwards |
| --- | --- | --- |
| Sentence search (`services/intent.py`) | Fills in a fixed form from a sentence | Ids must exist in the catalogue, numbers must be in range; the result only moves the controls, and the normal search runs |
| Questions (`services/rag.py`) | Writes an answer from retrieved document passages | No passage similar enough: fixed "no evidence" answer, no model call. An answer must cite passages, and every figure in it must be in a passage it cites; otherwise only the passages are shown |
| Area briefings (`services/briefing.py`) | Puts an area's rent, amenity and job figures into two or three sentences, offline | The text must name the area exactly and contain no figure or name that was not in its input. It is shown only while those figures are still current |

**Without a model.** With no `GEMINI_API_KEY`, a stand-in that is always
"unavailable" takes the place of the Gemini client (`infrastructure/ai_disabled.py`).
`POST /intent` and `POST /ask` then answer 503 with the code `ai_unavailable`,
the frontend hides the sentence box and the Ask view, and the search, the
comparison, the map and stored briefings work as before. The same happens
per request when the model times out (10 seconds) or its quota is used up.

**A fixed daily allowance.** The free tier allows a set number of requests per
model per day, and that is a hard limit here. Every request, from the API or
from a job, is counted in the `ai_usage` table before it is sent
(`infrastructure/budget.py`); at the limit nothing more is sent until Google's
next day starts at midnight Pacific time (`domain/quota.py`). A per-day refusal
from Google closes the day too. `/ai/status` then reports
`daily_limit_reached` with `resets_at`, the two endpoints answer 503 with the
code `ai_daily_limit` and `Retry-After`, and the frontend says when the
features are back. Limits: `AI_DAILY_TEXT_REQUESTS` (500) and
`AI_DAILY_EMBEDDING_REQUESTS` (1000). The SDK does not retry, because every
attempt counts, and every text in an embedding call counts as one request, as
Google counts it. Offline jobs also keep under the free tier's 100 embedded texts
a minute (`AI_EMBEDDING_TEXTS_PER_MINUTE`, 90).

**The document library.** Ask answers from the project's notes and from
official pages on an allow-list (`data/documents/sources.json`): sections of
the Residence Act and the Federal Registration Act, the Berlin and Munich
service pages for registering an address and the residence permit for
studies, the Minijob-Zentrale's page on student jobs, and the Verbraucherzentrale
page on the broadcasting fee. `jobs.fetch_documents` reads them offline, as an
identified program that follows robots.txt, skips pages that reserve text and
data mining, and waits two seconds between pages. The fetched text is not
committed and is shown word for word only where that is allowed (the laws,
which carry no copyright); for the other pages the app gives the answer and a
link. Pages that refuse identified programs (the German missions in India) are
left out.

**Jobs.** Nothing slow runs while a student waits except the two model calls
they ask for. Documents are embedded and briefings are written offline:

| Command (from `backend/`) | What it does |
| --- | --- |
| `uv run python -m jobs.check_ai` | One small call to each configured model |
| `uv run python -m jobs.fetch_documents` | Fetch the official pages on the allow-list (`data/documents/sources.json`) into `data/documents/fetched/` |
| `uv run python -m jobs.ingest_documents` | Cut `data/documents/*.md` and `fetched/*.md` into sections, embed them, store them in pgvector |
| `uv run python -m jobs.build_briefings --city munich` | Write the briefing of every area whose figures changed; `--limit N`, `--force`, `--written-before WHEN` (carry on with a rewrite that stopped) |

The models are set in `.env` (`GEMINI_TEXT_MODEL`, `GEMINI_EMBEDDING_MODEL`);
the defaults are `gemini-3.5-flash-lite` and `gemini-embedding-2`. Requests on
Google's free tier may be used by Google to improve its products, so the app
sends it only the sentence or question a student typed and public figures.

### Evaluation

`backend/evaluation/` measures this layer on labelled questions and sentences
(`backend/data/evaluation/`): which embedding model ranks the right document
section first, how well the similarity threshold separates covered from
uncovered questions, how many questions are answered with a correct source, and
how accurately a sentence becomes search settings. The labels were written for
this project and are few, so the figures show that the pipeline works; they do
not predict accuracy on real questions. Every model request the evaluation
makes counts against the same daily allowance as the app.

## Frontend

The interface is branded **Vilayat** ("abroad"), after the design in
`Vilayat.html` design prototype (not kept in the repository): newsprint paper, the Source Serif 4 typeface, India green as the
one interface colour, and the German and Indian flag colours as decoration.
Four pages, all in `frontend/src`:

- **Home** (`/`): what the app does, told as the page scrolls; photographs of
  the seven universities, cycling; a planner card that asks the API how many
  areas fit and opens the planner with those settings; and a question card that
  hands its question to the Ask page.
- **Planner** (`/planner`): pick a city and campus, set a rent ceiling and a
  commute limit, optionally pin an employer and adjust what matters most. The
  map shades the areas by rank and can show hexagon layers for commute,
  amenities and job access. Clicking an area opens its reasons, trade-off,
  facts with their sources, and links to rental portals.
- **Compare** (`/compare`): how many areas fit one budget around each university
  and campus, with each university's photograph.
- **Ask** (`/ask`): questions about moving, answered from the stored documents
  with numbered sources. `/ask?city=munich&q=...` asks a question on arrival.
  Shown only when a model is configured.

With a model configured, the planner also has a sentence box that fills in the
controls, and the area panel shows the stored briefing under "In short".

Information pages, linked from the footer: `/about` (how the ranking works),
`/data` (datasets, dates and licences, and what the asterisk means), `/ai`,
`/privacy`, `/terms` and `/contact`. Placeholder figures carry a small asterisk
that links to `/data#placeholder` instead of a warning box. Set
`NEXT_PUBLIC_CONTACT_EMAIL` in `.env` before building to show a contact address.

The university photographs are from Wikimedia Commons under free licences; each
is shown with its photographer and licence, as the licences require. The list is
in `frontend/public/universities/README.md` and `src/lib/universities.ts`.

| Folder | Contents |
| --- | --- |
| `src/lib/api/` | Zod schema and query hook for every endpoint; fixtures captured from the real API |
| `src/lib/` | Pure logic: address-bar state, formatting, map colours, applying a parsed sentence, splitting an answer at its source markers |
| `src/components/planner/` | Sentence box, constraint panel, results list, map, area detail |
| `src/components/home/` | Home page: hero photographs, the scroll story, the planner and question cards |
| `src/components/compare/` | Comparison view |
| `src/components/ask/` | Question view |
| `src/components/info/`, `src/app/{about,data,ai,privacy,terms,contact}/` | Information pages |

The base map comes from OpenFreeMap (OpenStreetMap data, no key needed). The map
library loads a worker file that `scripts/copy-map-worker.mjs` copies into
`public/maplibre/` before `pnpm dev` and `pnpm build`.

## API

Interactive documentation with every endpoint, schema and example:
<http://localhost:8000/docs>. All product endpoints live under `/api/v1`.

| Endpoint | Purpose |
| --- | --- |
| `GET /cities` | Cities the app covers |
| `GET /cities/{city}/universities` | Universities with their campuses |
| `GET /cities/{city}/employers` | Employer sites that can be pinned |
| `GET /cities/{city}/sources` | Publisher, licence and date of every dataset |
| `POST /search` | Rank areas for a campus, rent ceiling and commute limit |
| `GET /areas/{id}?campus_id=` | One area in detail, with links to rental portals |
| `GET /cities/{city}/comparison?max_rent_eur=&max_commute_minutes=` | Feasible areas per university |
| `GET /cities/{city}/layers/areas?campus_id=` | Area outlines as GeoJSON |
| `GET /cities/{city}/layers/cells?metric=&campus_id=` | Hexagon heatmap as GeoJSON (`commute`, `amenities`, `job_access`) |
| `GET /ai/status` | Whether a language model is configured |
| `POST /intent` | Turn a sentence into search settings |
| `POST /ask` | Answer a question from the stored documents, with citations |
| `GET /areas/{id}/briefing` | The stored briefing of an area; never calls a model |
| `GET /health` | Service status (unversioned) |

Conventions:

- A figure that is not known is the string `"UNKNOWN"`, never `null` or a guess.
- Every error has the shape `{"error": {"code", "message", "request_id", "details"}}`.
- Every response carries `X-Request-ID` and a `Server-Timing` header with the
  time each stage took; the same goes to the log, one line per request.
- One client address may make 120 requests a minute (`RATE_LIMIT_PER_MINUTE`);
  beyond that the answer is 429 with `Retry-After`. `POST /intent` and
  `POST /ask` together have a stricter limit of 10 a minute
  (`AI_RATE_LIMIT_PER_MINUTE`), because each uses the model's quota.
- When the model is switched off or does not answer, those two endpoints
  return 503 with the code `ai_unavailable`; when its daily allowance is used
  up, 503 with `ai_daily_limit` and `Retry-After`. No other endpoint needs the model.

Example (take a `campus_id` from the universities endpoint):

```bash
curl -s -X POST http://localhost:8000/api/v1/search -H "Content-Type: application/json" -d '{"campus_id": 8, "max_commute_minutes": 35, "max_rent_eur": 800}'
```

## Data and sources

| Data | Source | Licence | Status |
| --- | --- | --- | --- |
| Berlin areas (97 Ortsteile) | ALKIS Berlin Ortsteile, Geoportal Berlin | Datenlizenz Deutschland Zero 2.0 | Real, retrieved 2026-10-05 |
| Munich areas (25 Stadtbezirke) | Stadtbezirke München, Landeshauptstadt München, GeodatenService | Datenlizenz Deutschland Namensnennung 2.0 | Real, retrieved 2026-10-05 |
| Campus coordinates | OpenStreetMap (Nominatim geocoding of each campus address) | ODbL, © OpenStreetMap contributors | Real, retrieved 2026-10-05 |
| Places (amenities, student-type employers) | OpenStreetMap via the Overpass API | ODbL, © OpenStreetMap contributors | Real, retrieved 2026-10-05 |
| Job access score, job hotspots | Derived from the places above | as above | Computed; a proxy for where employers cluster, not vacancies |
| Area rents | `backend/data/rents/sample_rents.csv` | none | **Sample, synthetic, not real rents** |
| Employer sites | `backend/data/employers/sample_employers.csv` | coordinates: ODbL | **Sample: a proposed list, not confirmed** |
| Documents for question answering | `backend/data/documents/*.md` | none | **Sample: notes summarising ten official pages, not the official texts** |

Details and file formats are in the README of each folder under
[backend/data/](backend/data/): `boundaries`, `osm`, `rents`, `employers`,
`documents`, `evaluation`.
Cities are configured in `backend/cities/`; adding a city means adding one
module there.

To refresh the OpenStreetMap snapshot of a city (needs network), then reload:

```bash
cd backend && uv run python -m jobs.fetch_osm_places --city berlin
```

## Travel times

Public-transport travel times between every cell and every destination are
computed offline and stored in the `travel_times` table; the web backend only
looks them up. This step needs Java 21 and a few hundred MB of downloads, and is
only needed again when the timetables, the cells or the destinations change.

1. Download the timetable (GTFS) and street (OpenStreetMap) files of a city into
   `backend/data/raw/`, which is not committed:

   ```bash
   cd backend && uv run python -m jobs.fetch_feeds --city munich
   ```

2. Compute and store the travel times. `--group routing` installs the routing
   engine's Python packages; the first run also downloads the engine itself
   (R5, 64 MB) and builds the network, which it caches for later runs:

   ```bash
   cd backend && uv run --group routing python -m jobs.build_travel_times --city munich
   ```

   Munich takes about 4 minutes. Berlin takes about 20, of which 6 are a
   one-time network build; it can be run in slices, each replacing only the
   travel times of its own cells:

   ```bash
   cd backend && uv run --group routing python -m jobs.build_travel_times --city berlin --part 1/3
   ```

   Repeat with `--part 2/3` and `--part 3/3`, then compute the few
   destination-to-destination times (campus to employer), which a slice leaves
   out. Add `--max-memory 6G` to any of these to cap the routing engine's memory.

   ```bash
   cd backend && uv run --group routing python -m jobs.build_travel_times --city berlin --destinations-only
   ```

3. Spot-check the result against a few journeys of known rough duration:

   ```bash
   cd backend && uv run python -m jobs.check_travel_times
   ```

What is stored: the median door-to-door time (walking at 4.8 km/h, waiting,
riding and changing) for a weekday morning from home to the destination (leaving
07:30 to 09:00) and for the evening from the destination back home (leaving
17:00 to 19:00). "Home" is the centre of a cell, moved to the nearest street. A
pair with no journey within two hours has no row and shows as UNKNOWN.

Before routing, each timetable is trimmed to the city plus about 10 km
(`jobs/gtfs_prepare.py`), because a regional feed is too large for a laptop's
memory. The travel times exist only in the database: they are not committed, and
`docker compose down -v` deletes them.

### Typical journeys (route breakdown)

The travel times say how long, not how. For the step-by-step view, one typical
morning journey per area and campus is planned with the same engine and stored
in `commute_routes`:

```bash
cd backend && uv run --group routing python -m jobs.build_commute_routes --city munich
```

It starts from the hexagon whose time is closest to the area's median and keeps
the option (leaving 07:30 to 09:00) whose length is closest to that hexagon's
median, so it shows a typical trip, not the best case. Line names come from the
timetable's `routes.txt`; stop names from the stop nearest each ride's ends
(`jobs/gtfs_names.py`), because the engine shortens German stop ids. About 8
seconds per journey: Munich (150) about 20 minutes, Berlin (679) about 1.5
hours. A stopped run keeps its work, and running again carries on.
`GET /api/v1/areas/{id}/commute?campus_id=` returns the journey and the spread
(fastest, median, slowest over the area's hexagons).

| Timetable and street data | Publisher | Licence |
| --- | --- | --- |
| Berlin timetable (GTFS) | VBB Verkehrsverbund Berlin-Brandenburg GmbH | CC BY 4.0 |
| Munich timetable (GTFS) | Münchner Verkehrs- und Tarifverbund GmbH (MVV) | CC BY |
| Street networks | OpenStreetMap contributors (extracts by Geofabrik and BBBike) | ODbL |

## Database migrations

The schema is defined in `backend/infrastructure/db/models.py` and changed only
through Alembic migrations in `backend/migrations/versions/`. From `backend/`:

| Command | What it does |
| --- | --- |
| `uv run alembic upgrade head` | Apply every migration not yet applied |
| `uv run alembic current` | Show which migration the database is at |
| `uv run alembic check` | Fail if the models and the database differ |
| `uv run alembic revision --autogenerate -m "message"` | Draft a migration from model changes (review it before use) |
| `uv run alembic upgrade head --sql` | Print the SQL without running it |

## Checks

Backend, from `backend/`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

- Unit tests only (no database): `uv run pytest -m "not integration"`
- Integration tests need `docker compose up -d db`. They fail, rather than skip,
  when the database is down.
- Integration tests use their own database, `educommute_test`, which is dropped
  and rebuilt from the migrations on every run. The development data is never
  touched.

The tests never call a real model: `tests/conftest.py` blanks the API key for
the test run, and the AI services are tested with scripted fakes.

Frontend, from `frontend/`:

```bash
pnpm lint && pnpm typecheck && pnpm format:check && pnpm test && pnpm build
```

`pnpm test` runs Vitest on the schemas and the pure logic. The schema tests
parse responses captured from the real backend, so they fail if the two drift
apart.

`pnpm build` writes the static site to `frontend/out/`.

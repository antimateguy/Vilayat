# Where the data lives

Everything Vilayat shows is prepared offline by the jobs in `backend/jobs/` and
stored in two places: **files in the repository** (inputs that are small enough
to keep in Git) and **the PostgreSQL database** (everything the website reads).
The website never computes a route, calls a portal or downloads anything while
a visitor waits; it only reads the database.

A ready-made copy of the whole database is kept in `db/seed/vilayat.dump`
(3.5 MB). A new local database loads it on its first start, and a hosted one is
filled from it in one command (see [deployment.md](deployment.md)).

## 1. Files in the repository (`backend/data/`)

| Folder | What is in it | Made by | In Git? |
| --- | --- | --- | --- |
| `boundaries/` | Official district outlines: Berlin's 97 Ortsteile, Munich's 25 Stadtbezirke (GeoJSON, 2.5 MB) | Downloaded once from the city geoportals; `README.md` names the source | Yes |
| `osm/` | Snapshot of the OpenStreetMap places used for amenities and job access (`*_places.tsv`, 1.9 MB) with the download date (`*.meta.json`) | `jobs.fetch_osm_places` | Yes |
| `rents/` | `sample_rents.csv`: **placeholder** rent per area until real data is supplied | `jobs.make_sample_rents` | Yes |
| `employers/` | `sample_employers.csv`: **placeholder** list of large employers | Written by hand | Yes |
| `documents/` | The notes the Ask page answers from (Markdown, one per topic, with source URL and date), and `sources.json`, the allow-list of official pages | Written for the project | Yes |
| `documents/fetched/` | Text of the official pages on the allow-list, one Markdown file each, with source and date | `jobs.fetch_documents` | **No**: stored to be searched, not redistributed |
| `evaluation/` | Test questions and sentences for the AI evaluation | Written by hand | Yes |
| `raw/<city>/` | Timetables (GTFS zip) and street network (OpenStreetMap `.osm.pbf`), about 160 to 190 MB per city, with `.meta.json` download dates | `jobs.fetch_feeds` | **No**: too large; downloaded again when needed |
| `cache/` | Temporary downloads | Jobs | **No** |

The city settings (universities, campuses, feed URLs, listing portals, map
bounds) are code, not data files: `backend/cities/berlin.py` and `munich.py`.

## 2. The database (PostgreSQL with PostGIS and pgvector)

Locally the database runs in Docker; its files live in the Docker volume
`educommute_db_data`, so they survive `docker compose down` (but not
`docker compose down -v`). The schema is created by the Alembic migrations in
`backend/migrations/versions/`. About 60 MB in total.

| Table | What it holds | Written by |
| --- | --- | --- |
| `cities`, `universities`, `campuses` | The two cities, their universities and campus sites | `jobs.load_base_data` (from `backend/cities/`) |
| `destinations` | Every point travel times are computed to: campuses, job hotspots, employer sites | `jobs.load_base_data` |
| `neighbourhoods` | The areas that are ranked, with their outlines | `jobs.load_base_data` (from `data/boundaries/`) |
| `cells` | H3 hexagons (about 0.7 km² each) inside each area, with job access per hexagon | `jobs.load_base_data` |
| `places` | Supermarkets, cafés, libraries, gyms, shops and so on | `jobs.load_base_data` (from `data/osm/`) |
| `area_rents` | Rent per area, with source and date (currently placeholder) | `jobs.load_rents` (from `data/rents/`) |
| `travel_times` | Minutes by public transport from every hexagon to every destination, morning and evening (median over the departure window) | `jobs.build_travel_times` (from `data/raw/`; needs Java) |
| `destination_travel_times` | Minutes between destinations, for example campus to employer | `jobs.build_travel_times` |
| `commute_routes` | One typical journey per area and campus: walk, line and stops, walk, with the path for the map | `jobs.build_commute_routes` (from `data/raw/`; needs Java) |
| `destination_routes` | One typical afternoon journey from every campus to every employer | `jobs.build_commute_routes` |
| `doc_chunks` | The Ask documents cut into sections, with their embedding vectors | `jobs.ingest_documents` (from `data/documents/`; uses the embedding model) |
| `area_briefings` | The short AI summary of each area ("In short"), with the figures it was written from | `jobs.build_briefings` (uses the text model) |
| `ai_usage` | How many model requests were made on each day, per model, to keep inside the free allowance | The API and the AI jobs, on every model request |

## 3. Rebuilding everything from scratch

```bash
docker compose up -d db
cd backend
uv run alembic upgrade head
uv run python -m jobs.load_base_data
uv run python -m jobs.fetch_feeds --city munich
uv run --group routing python -m jobs.build_travel_times --city munich
uv run --group routing python -m jobs.build_commute_routes --city munich
uv run python -m jobs.fetch_documents
uv run python -m jobs.ingest_documents
uv run python -m jobs.build_briefings --city munich
```

Repeat the city-specific lines for Berlin. The last two use the Gemini API and
count against the daily free allowance.

## 4. Things that are not stored anywhere

- Nothing about visitors: no accounts, no cookies, no search history. Search
  settings live only in the page address.
- No housing listings and no job ads: the app links to the portals instead.
- No live routing: every travel time and route is computed in advance.

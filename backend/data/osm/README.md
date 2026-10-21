# OpenStreetMap places

Snapshots of the points of interest the app uses, one pair of files per city:

- `<city>_places.tsv`: tab-separated, one place per line, with its OpenStreetMap
  type and id, coordinate, name and the `shop`, `amenity` and `leisure` tags.
- `<city>_places.meta.json`: retrieval date, the server that answered and the
  exact query.

The data is © OpenStreetMap contributors, available under the Open Database
License (ODbL): <https://www.openstreetmap.org/copyright>. The site credits
OpenStreetMap on the map and on its Data and sources page.

| City | Places | Retrieved |
| --- | --- | --- |
| Berlin | 21,271 | 2026-10-05 |
| Munich | 9,059 | 2026-10-05 |

Each snapshot covers the city plus a margin of about 3 km, so that businesses
just across the boundary still count for homes at the edge.

## What counts as which category

Defined in `backend/jobs/osm_tags.py`:

| Category | OpenStreetMap tags |
| --- | --- |
| supermarket | `shop=supermarket` |
| cafe | `amenity=cafe` |
| library | `amenity=library` |
| gym | `leisure=fitness_centre` |
| restaurant | `amenity=restaurant`, `amenity=fast_food` |
| bar | `amenity=bar`, `amenity=pub` |
| retail | `shop=` clothes, shoes, department_store, convenience, bakery, chemist, electronics, books |

Supermarket, cafe, library and gym are the walkable amenities. Cafe, restaurant,
bar, retail and supermarket are the businesses that typically hire students.

## Refreshing a snapshot

```bash
uv run python -m jobs.fetch_osm_places --city berlin
```

Then reload with `uv run python -m jobs.load_base_data`. The download tries the
main public Overpass server first and falls back to a second public instance.

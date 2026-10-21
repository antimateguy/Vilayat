# Neighbourhood boundaries

Official administrative boundaries, downloaded once and kept in the repository so
that loading the base data needs no network access and always gives the same
result. Coordinates are WGS84 (EPSG:4326), longitude first.

| File | Dataset | Publisher | Licence | Retrieved |
| --- | --- | --- | --- | --- |
| `berlin_ortsteile.geojson` | ALKIS Berlin Ortsteile (97 localities) | Geoportal Berlin | [Datenlizenz Deutschland - Zero - Version 2.0](https://www.govdata.de/dl-de/zero-2-0) | 2026-10-05 |
| `munich_stadtbezirke.geojson` | Stadtbezirke München (25 city districts) | Landeshauptstadt München, GeodatenService | [Datenlizenz Deutschland - Namensnennung - Version 2.0](https://www.govdata.de/dl-de/by-2-0) | 2026-10-05 |

The Munich licence requires attribution: "Landeshauptstadt München,
GeodatenService", with the licence named. The site shows it on the map and on
its Data and sources page.

The Munich file has 27 features for 25 districts: a district with a detached
part is listed once per part. The loader merges them.

## Downloading again

The exact request URLs are in `backend/cities/berlin.py` and
`backend/cities/munich.py` (`boundaries.url`). After a new download, update
`retrieved_on` in the same file and run `uv run python -m jobs.load_base_data`.

# Employer sites

## `sample_employers.csv` is a proposed list, not a confirmed one

The curated list of corporate employer sites has not been supplied yet.
`sample_employers.csv` is a stand-in: ten well-known sites per city. Each
address was turned into a coordinate with OpenStreetMap's geocoder (Nominatim,
© OpenStreetMap contributors, ODbL), which confirms that the address exists but
not that the company is at it. Every row therefore has `is_sample=true`, and the
app labels these sites as sample data.

Two Munich-region sites lie outside the city boundary (Infineon in Neubiberg,
SAP in Garching). That is fine: an employer is a travel destination, not an area.

## Supplying the real list

Provide a CSV file (UTF-8, comma-separated, with this header row) and load it:

```bash
uv run python -m jobs.load_employers path/to/employers.csv
```

| Column | Meaning | Example |
| --- | --- | --- |
| `city_id` | `berlin` or `munich` | `munich` |
| `name` | Shown to the student; unique within the city | `BMW Group Headquarters` |
| `address` | For readers; not used by the loader | `Petuelring 130, 80809 München` |
| `lat`, `lon` | WGS84 coordinate of the site | `48.17691`, `11.56013` |
| `source` | Where the entry and its coordinate come from | `Company website, checked by hand` |
| `source_url` | Link to the source; may be empty | |
| `as_of` | Date the entry was checked, `YYYY-MM-DD` | `2026-10-05` |
| `is_sample` | `true` or `false`; `false` once confirmed | `false` |

Loading a file makes each city in it match the file exactly: sites that are no
longer listed are removed, and a site that keeps its name keeps its stored
travel times.

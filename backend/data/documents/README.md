# Documents for question answering

## The files here are sample notes, not official texts

Real documents have not been supplied yet. Each file in this folder is a short
note written for this project. It summarises one official page, which is named
in `source_url` and was read on the date in `retrieved_on`. The notes are not
the official wording, are not checked by the publishers, and will go out of
date. Every file therefore has `is_sample: true`, and the app puts an asterisk
next to every source an answer cites, explained on the Data and sources page.
Do not rely on them for a visa, permit or contract decision; follow the link to
the official page.

Two topics were left out because the official pages could not be read
automatically: the semester ticket in Berlin and the halls of residence in
Munich. Questions about them get the "no evidence" answer.

## Official pages (the larger library)

`sources.json` lists the official pages the library is built from, and the
only domains they may come from. `uv run python -m jobs.fetch_documents` reads
each page (identified, following robots.txt, skipping pages that reserve text
and data mining, two seconds apart) and writes `fetched/<key>.md` in the format
below, with `is_sample: false` and `can_quote`. `fetched/` is not committed.
`can_quote: true` only for German laws, which are official works without
copyright; for the other pages the app answers and links but does not show the
text. To add a page, add an entry to `sources.json` and run both jobs.

## Supplying real documents

Put one Markdown file per document in this folder and run:

```bash
uv run python -m jobs.ingest_documents
```

The store is made to match the folder: changed files are replaced and files
that were removed here are deleted from the store.

A file starts with a header, followed by the text. A line starting with `## `
begins a section, and each section becomes one searchable chunk.

```markdown
---
title: Registering your address in Berlin
source_url: https://service.berlin.de/dienstleistung/120686/
retrieved_on: 2026-10-06
city: berlin
is_sample: false
---
## Deadline and place

In Berlin you must register ...
```

| Key | Meaning |
| --- | --- |
| `title` | Shown with every citation |
| `source_url` | Link to the official page; must start with `https://` |
| `retrieved_on` | Date the page was read, `YYYY-MM-DD` |
| `city` | `berlin` or `munich`; empty for a document that applies everywhere |
| `is_sample` | `true` for a note like the ones here; `false` for an official text |

The file name without `.md` is the document's key. Check that the publisher's
licence allows the text to be stored and shown before adding it.

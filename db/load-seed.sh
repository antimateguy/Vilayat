#!/bin/sh
# Loads db/seed/vilayat.dump into a hosted database (Neon), from the address in
# PRODUCTION_DATABASE_URL. Run from the repository root, in any shell:
#
#   docker run --rm --env-file .env -v ./db:/db:ro educommute-db:17 sh /db/load-seed.sh
#
# It connects directly, not through Neon's connection pooler: pg_restore sets
# session options that a pooled connection would pass on to the next client.
set -eu
: "${PRODUCTION_DATABASE_URL:?Put the hosted database address in .env as PRODUCTION_DATABASE_URL=...}"
DIRECT=$(printf %s "$PRODUCTION_DATABASE_URL" | sed "s/-pooler//")

psql "$DIRECT" -v ON_ERROR_STOP=1 -q \
    -c "CREATE EXTENSION IF NOT EXISTS postgis" \
    -c "CREATE EXTENSION IF NOT EXISTS vector"
# --clean --if-exists replaces what an earlier load left, so it can be rerun.
pg_restore --clean --if-exists --no-owner --no-privileges --dbname "$DIRECT" /db/seed/vilayat.dump
psql "$DIRECT" -tA -c "SELECT count(*) || ' areas loaded' FROM neighbourhoods"

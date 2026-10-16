#!/bin/sh
# Makes db/seed/vilayat.dump: the whole prepared database, ready to load, so a
# fresh clone (or a hosted database) needs none of the offline jobs.
#
# Run from the repository root while the stack is up:
#   docker compose exec -T db sh -s < db/make-seed.sh
#   docker compose cp db:/tmp/vilayat.dump db/seed/vilayat.dump
#
# Left out of the dump, by deleting them from a scratch copy:
# - the text fetched from official pages that may not be republished
#   (doc_chunks with can_quote = false; jobs.fetch_documents gets them back);
# - the daily count of AI requests, which belongs to one installation.
set -eu
DB="${POSTGRES_DB:-educommute}"
USER="${POSTGRES_USER:-educommute}"
SCRATCH=vilayat_seed

pg_dump -U "$USER" -d "$DB" -Fc -f /tmp/full.dump
dropdb -U "$USER" --if-exists "$SCRATCH"
createdb -U "$USER" "$SCRATCH"
pg_restore -U "$USER" -d "$SCRATCH" --no-owner --no-privileges /tmp/full.dump
psql -U "$USER" -d "$SCRATCH" -v ON_ERROR_STOP=1 -q <<'SQL'
DELETE FROM doc_chunks WHERE NOT can_quote;
DELETE FROM ai_usage;
SQL
pg_dump -U "$USER" -d "$SCRATCH" -Fc -Z 9 --no-owner --no-privileges -f /tmp/vilayat.dump
dropdb -U "$USER" "$SCRATCH"
rm -f /tmp/full.dump
ls -la /tmp/vilayat.dump

#!/bin/sh
# Runs once, on the first start of an empty data volume: loads the prepared
# data (areas, travel times, journeys, documents, summaries) from the seed
# dump, so the site works straight after `docker compose up`. Without the file
# the database simply starts empty.
set -eu
SEED=/seed/vilayat.dump
if [ ! -f "$SEED" ]; then
    echo "No seed dump at $SEED; starting with an empty database."
    exit 0
fi
echo "Loading the seed data from $SEED..."
pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --no-owner --no-privileges --exit-on-error "$SEED"
echo "Seed data loaded."

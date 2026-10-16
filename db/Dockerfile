# Postgres 17 with PostGIS 3 and pgvector.
# No official image ships both extensions, so both are installed on the official
# Postgres image from the PostgreSQL project's apt repository, which that image
# already has configured. (The postgis/postgis image is not used as the base: it
# sits on a Debian release the repository no longer serves, so pgvector cannot
# be added to it.)
FROM postgres:17-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-17-postgis-3 \
        postgresql-17-postgis-3-scripts \
        postgresql-17-pgvector \
    && rm -rf /var/lib/apt/lists/*

# Scripts in this directory run once, when the data volume is first created.
COPY init/ /docker-entrypoint-initdb.d/

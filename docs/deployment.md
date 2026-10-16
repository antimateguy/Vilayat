# Deployment

Vilayat runs on three free services:

| Part | Service | Free plan notes |
| --- | --- | --- |
| Website (static files) | Cloudflare Pages | Unlimited requests; builds on every push |
| API (Docker container) | Render | Sleeps after 15 idle minutes; waking takes up to a minute |
| Database (PostgreSQL with PostGIS and pgvector) | Neon | 0.5 GB storage; sleeps when idle and wakes in about a second |

GitHub Actions checks every push (lint, types, tests, build). Render deploys the
API only after those checks pass; Cloudflare Pages builds the site by itself.

## What stays private

- **The Gemini API key and the database password** are stored only in Render's
  environment settings (encrypted, visible to the account owner) and in your
  local `.env`, which Git ignores. They are never in the repository, never in
  GitHub Actions and never sent to the browser: the website talks to the API,
  and only the API talks to Gemini and the database.
- **The website's settings** (`NEXT_PUBLIC_*`) are built into public JavaScript,
  so they must never hold a secret. They only hold the API's public address.
- The repository can be public: it holds code, the prepared data and no secrets.

## 1. Database: Neon

1. Sign up at <https://neon.tech> and create a project: PostgreSQL 17, region
   **AWS Europe Central (Frankfurt)**, close to Render's Frankfurt region.
2. On the project dashboard, choose **Connect** and copy the connection string.
   It looks like
   `postgresql://user:password@ep-....eu-central-1.aws.neon.tech/neondb?sslmode=require`.
3. Put it in the repository's `.env` (never in a chat or a commit) as
   `PRODUCTION_DATABASE_URL=...`.
4. Load the prepared data (needs Docker; reads the address from `.env`, so it
   is never printed):

   ```bash
   docker run --rm --env-file .env -v "$(pwd)/db/seed:/seed:ro" educommute-db:17 sh -c 'psql "$PRODUCTION_DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS vector;" && pg_restore --no-owner --no-privileges --dbname "$PRODUCTION_DATABASE_URL" /seed/vilayat.dump'
   ```

   Later schema changes are applied by the API itself when it starts
   (`alembic upgrade head`).

## 2. API: Render

1. Sign up at <https://render.com> with your GitHub account and allow it to
   read the repository.
2. **New > Blueprint**, pick the repository. Render reads `render.yaml` and
   asks for three values:
   - `DATABASE_URL`: the Neon connection string from step 1.
   - `GEMINI_API_KEY`: your key from Google AI Studio (leave empty to run
     without the AI features).
   - `CORS_ORIGINS`: the website's address from step 3, for example
     `https://vilayat.pages.dev` (fill in after step 3, then redeploy).
3. After the first deploy the API is at an address like
   `https://vilayat-api.onrender.com`. Check `https://<that address>/health`.

## 3. Website: Cloudflare Pages

1. Sign up at <https://dash.cloudflare.com>, then **Workers & Pages > Create >
   Pages > Connect to Git**, and pick the repository.
2. Build settings:

   | Setting | Value |
   | --- | --- |
   | Framework preset | None |
   | Root directory | `frontend` |
   | Build command | `npx --yes pnpm@12.9.1 install --frozen-lockfile && npx --yes pnpm@12.9.1 run build` |
   | Build output directory | `out` |
   | Environment variable `NODE_VERSION` | `24` |
   | Environment variable `NEXT_PUBLIC_API_BASE_URL` | the Render address from step 2 |
   | Environment variable `NEXT_PUBLIC_CONTACT_EMAIL` | optional: an address for the Contact page |

3. The site is published at `https://<project>.pages.dev`. Put that address in
   Render's `CORS_ORIGINS` (step 2) so the browser may call the API.

## 4. Keeping the API awake (optional)

Render's free API sleeps after 15 idle minutes. `.github/workflows/keep-warm.yml`
pings its liveness check every 14 minutes from 07:30 to 23:30 India time. Turn it
on in GitHub: **Settings > Secrets and variables > Actions > Variables > New
repository variable**, name `API_URL`, value the Render address. The ping does
not touch the database, so Neon can still sleep and stay inside its free hours.

## Measuring

Record cold and warm response times after deploying, for example:

```bash
curl -o /dev/null -s -w "%{time_total}\n" https://vilayat-api.onrender.com/api/v1/cities
```

Run it once after the API has slept (cold) and again straight after (warm).

## Updating the data

The offline jobs run on a developer machine (see the
[developer guide](developer-guide.md)). After changing data, make a new seed and
load it into Neon again:

```bash
docker compose exec -T db sh -s < db/make-seed.sh
```

```bash
docker compose cp db:/tmp/vilayat.dump db/seed/vilayat.dump
```

The seed leaves out the text fetched from official pages, which may not be
republished. To give the hosted Ask page those pages too, run
`jobs.fetch_documents` and `jobs.ingest_documents` against the hosted database
(set `DATABASE_URL` to the Neon address for that one command).

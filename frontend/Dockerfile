# Frontend image for local use: builds the static site, then serves it.
# In production the same static files go to a CDN (Cloudflare Pages) instead.

# --- Stage 1: build the static export into /app/out -------------------------
FROM node:24-slim AS build

# The version matches "packageManager" in package.json.
RUN npm install --global pnpm@12.9.1

WORKDIR /app

# Dependencies first: this layer is rebuilt only when the lock file changes.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

# The address the browser calls the API at. It is fixed into the JavaScript at
# build time, so changing it means building the image again.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
# Optional address shown on the Contact page; left empty, none is shown.
ARG NEXT_PUBLIC_CONTACT_EMAIL=
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}     NEXT_PUBLIC_CONTACT_EMAIL=${NEXT_PUBLIC_CONTACT_EMAIL} \
    NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

# --- Stage 2: serve the files; no Node.js in the final image ------------------
FROM nginx:1.29-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/out /usr/share/nginx/html

EXPOSE 3000

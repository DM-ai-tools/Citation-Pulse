# Works when Railway Root Directory is ``apps/web`` OR monorepo root with Dockerfile path ``apps/web/Dockerfile``.
FROM node:22-alpine AS deps

WORKDIR /app

COPY . /ctx

RUN set -eux; \
    if [ -f /ctx/apps/web/package.json ]; then \
      cp /ctx/package.json /ctx/package-lock.json /app/ 2>/dev/null || true; \
      mkdir -p /app/apps/web; \
      cp /ctx/apps/web/package.json /app/apps/web/package.json; \
      if [ -d /ctx/packages ]; then cp -r /ctx/packages /app/packages; fi; \
    elif [ -f /ctx/package.json ]; then \
      cp /ctx/package.json /ctx/package-lock.json /app/ 2>/dev/null || cp /ctx/package.json /app/; \
    else \
      echo "ERROR: no package.json in build context"; exit 1; \
    fi; \
    cd /app && (npm ci || npm install)

FROM node:22-alpine AS build

WORKDIR /app

ENV NODE_ENV=production

ARG NEXT_PUBLIC_API_URL
ARG API_PROXY_TARGET
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_DASHBOARD_SCAN_ID
ARG NEXT_PUBLIC_DASHBOARD_BRAND_ID
ARG NEXT_PUBLIC_DASHBOARD_SITE_URL
ARG NEXT_PUBLIC_APP_VERSION
ARG NEXT_PUBLIC_SKIP_AUTH=true

ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_SKIP_AUTH=${NEXT_PUBLIC_SKIP_AUTH}
ENV API_PROXY_TARGET=${API_PROXY_TARGET}
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}
ENV NEXT_PUBLIC_DASHBOARD_SCAN_ID=${NEXT_PUBLIC_DASHBOARD_SCAN_ID}
ENV NEXT_PUBLIC_DASHBOARD_BRAND_ID=${NEXT_PUBLIC_DASHBOARD_BRAND_ID}
ENV NEXT_PUBLIC_DASHBOARD_SITE_URL=${NEXT_PUBLIC_DASHBOARD_SITE_URL}
ENV NEXT_PUBLIC_APP_VERSION=${NEXT_PUBLIC_APP_VERSION}

COPY . /ctx

RUN set -eux; \
    cp -a /ctx/. /app/; \
    rm -rf /app/node_modules

COPY --from=deps /app/node_modules ./node_modules

RUN set -eux; \
    if [ -f /app/apps/web/package.json ]; then WEB=/app/apps/web; else WEB=/app; fi; \
    if [ -z "${NEXT_PUBLIC_API_URL:-}" ]; then \
      echo "CitationPulse WARNING: NEXT_PUBLIC_API_URL is empty during docker build."; \
    else \
      echo "CitationPulse: NEXT_PUBLIC_API_URL is set for next build."; \
    fi; \
    if [ -n "${API_PROXY_TARGET:-}" ] && [ -z "${NEXT_PUBLIC_API_URL:-}" ]; then \
      export NEXT_PUBLIC_API_URL=same-origin; \
      echo "CitationPulse: NEXT_PUBLIC_API_URL=same-origin (API_PROXY_TARGET set)."; \
    fi; \
    if [ -f /app/apps/web/package.json ]; then \
      npm run build -w citationpulse-web; \
    else \
      cd "$WEB" && npm run build; \
    fi; \
    mkdir -p /out; \
    cp -r "$WEB/.next" /out/.next; \
    cp "$WEB/package.json" /out/package.json; \
    cp "$WEB/next.config.ts" /out/next.config.ts; \
    if [ -f "$WEB/next.config.mjs" ]; then cp "$WEB/next.config.mjs" /out/next.config.mjs; fi; \
    if [ -f "$WEB/next.config.js" ]; then cp "$WEB/next.config.js" /out/next.config.js; fi; \
    if [ -d "$WEB/public" ]; then cp -r "$WEB/public" /out/public; else mkdir -p /out/public; fi

FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=build /out/ ./
COPY --from=build /app/node_modules ./node_modules

RUN npm prune --omit=dev 2>/dev/null || true

EXPOSE 3000

CMD ["sh", "-c", "npm run start -- --hostname 0.0.0.0 --port ${PORT:-3000}"]

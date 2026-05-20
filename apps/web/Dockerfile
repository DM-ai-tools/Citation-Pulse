FROM node:22-alpine AS deps

WORKDIR /app

COPY package*.json ./
RUN npm ci || npm install

FROM node:22-alpine AS build

WORKDIR /app

ARG NEXT_PUBLIC_API_URL
ARG API_PROXY_TARGET
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_DASHBOARD_SCAN_ID
ARG NEXT_PUBLIC_DASHBOARD_BRAND_ID
ARG NEXT_PUBLIC_DASHBOARD_SITE_URL
# Optional: set to git SHA or release label in CI/Railway so production can confirm deploy revision.
ARG NEXT_PUBLIC_APP_VERSION

ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV API_PROXY_TARGET=${API_PROXY_TARGET}
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}
ENV NEXT_PUBLIC_DASHBOARD_SCAN_ID=${NEXT_PUBLIC_DASHBOARD_SCAN_ID}
ENV NEXT_PUBLIC_DASHBOARD_BRAND_ID=${NEXT_PUBLIC_DASHBOARD_BRAND_ID}
ENV NEXT_PUBLIC_DASHBOARD_SITE_URL=${NEXT_PUBLIC_DASHBOARD_SITE_URL}
ENV NEXT_PUBLIC_APP_VERSION=${NEXT_PUBLIC_APP_VERSION}

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Next.js inlines NEXT_PUBLIC_* at `next build`. If this is empty here, the browser bundle will
# still use the code fallback (localhost) even when Railway shows the variable at runtime.
RUN if [ -z "${NEXT_PUBLIC_API_URL:-}" ]; then \
      echo "CitationPulse WARNING: NEXT_PUBLIC_API_URL is empty during docker build — client may call localhost. On Railway: set the variable on the Web service, then redeploy with rebuild (clear build cache if the warning persists)."; \
    else \
      echo "CitationPulse: NEXT_PUBLIC_API_URL is set for next build (length OK)."; \
    fi && \
    if [ -n "${API_PROXY_TARGET:-}" ] && [ -z "${NEXT_PUBLIC_API_URL:-}" ]; then \
      export NEXT_PUBLIC_API_URL=same-origin; \
      echo "CitationPulse: NEXT_PUBLIC_API_URL=same-origin (API_PROXY_TARGET set)."; \
    fi && \
    npm run build

FROM node:22-alpine

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./

EXPOSE 3000

CMD ["sh", "-c", "npm run start -- --port ${PORT:-3000}"]

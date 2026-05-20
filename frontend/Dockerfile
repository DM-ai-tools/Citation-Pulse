FROM node:22-alpine AS deps

WORKDIR /app

# Legacy Railway service may still point to frontend/Dockerfile.
# Build canonical monorepo web app (apps/web) so production reflects new auth UI/routes.
COPY package*.json ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages ./packages

RUN npm ci || npm install

FROM node:22-alpine AS build

WORKDIR /app

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

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build -w citationpulse-web

FROM node:22-alpine

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

COPY --from=build /app/apps/web/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/apps/web/package.json ./package.json

EXPOSE 3000

CMD ["sh", "-c", "npm run start -- --hostname 0.0.0.0 --port ${PORT:-3000}"]

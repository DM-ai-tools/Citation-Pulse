FROM node:22-alpine AS deps

WORKDIR /app

# Copy package files from repo root → frontend/ subfolder
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

FROM node:22-alpine AS build

WORKDIR /app

ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_DASHBOARD_SCAN_ID
ARG NEXT_PUBLIC_DASHBOARD_BRAND_ID
ARG NEXT_PUBLIC_DASHBOARD_SITE_URL

ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}
ENV NEXT_PUBLIC_DASHBOARD_SCAN_ID=${NEXT_PUBLIC_DASHBOARD_SCAN_ID}
ENV NEXT_PUBLIC_DASHBOARD_BRAND_ID=${NEXT_PUBLIC_DASHBOARD_BRAND_ID}
ENV NEXT_PUBLIC_DASHBOARD_SITE_URL=${NEXT_PUBLIC_DASHBOARD_SITE_URL}

COPY --from=deps /app/node_modules ./node_modules
# Copy entire frontend folder as build context
COPY frontend/ .

RUN npm run build

FROM node:22-alpine

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./

EXPOSE 3000

CMD ["sh", "-c", "npm run start -- --port ${PORT:-3000}"]

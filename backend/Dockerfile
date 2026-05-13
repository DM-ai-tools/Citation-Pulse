FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Source of truth is `apps/api/` (monorepo layout); `backend/` is kept only because
# Railway's existing service is still wired to `backend/railway.json`. Copying from
# `apps/api/` here ensures production runs the same code we develop against locally.
COPY apps/api/pyproject.toml apps/api/README.md ./
COPY apps/api/src ./src

RUN pip install --no-cache-dir -e .

EXPOSE 8000

# Trust proxy headers from Railway's edge (default uvicorn allow-list is 127.0.0.1 only).
CMD ["sh", "-c", "uvicorn citationpulse.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips \"*\""]

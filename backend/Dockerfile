# Railway: set service Root Directory to ``backend`` (Settings → Root Directory).
# Build context must be the ``backend/`` folder so ``COPY src`` exists.
# If Root Directory is the repo root, use ``backend/Dockerfile.monorepo-root`` instead.
#
# Build VMs are memory-limited; exit 137 during pip install = OOM (see infra/railway/README.md).
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

COPY pyproject.toml README.md ./
COPY src ./src

# Non-editable install (production). Playwright is optional — not needed for LLM scan engines.
RUN pip install --no-cache-dir --no-compile .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn citationpulse.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips \"*\""]

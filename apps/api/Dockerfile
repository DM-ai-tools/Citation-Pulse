# Works when Railway Root Directory is ``apps/api`` OR monorepo root with Dockerfile path ``apps/api/Dockerfile``.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

COPY . /ctx

RUN set -eux; \
    if [ -f /ctx/apps/api/pyproject.toml ]; then APP=/ctx/apps/api; \
    elif [ -f /ctx/pyproject.toml ]; then APP=/ctx; \
    else echo "ERROR: no apps/api/pyproject.toml in build context"; ls -la /ctx; exit 1; fi; \
    cp "$APP/pyproject.toml" .; \
    if [ -f "$APP/README.md" ]; then cp "$APP/README.md" .; fi; \
    cp -r "$APP/src" ./src; \
    pip install --no-cache-dir --no-compile .

EXPOSE 8000

# Trust proxy headers from Railway's edge (default uvicorn allow-list is 127.0.0.1 only).
CMD ["sh", "-c", "uvicorn citationpulse.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips \"*\""]

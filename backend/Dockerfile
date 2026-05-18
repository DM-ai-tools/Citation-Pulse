# Works whether Railway Root Directory is ``backend`` or the monorepo root (``backend/Dockerfile``).
# Build VMs are memory-limited; exit 137 on pip install = OOM — see infra/railway/README.md.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

COPY . /ctx

RUN set -eux; \
    if [ -f /ctx/backend/pyproject.toml ]; then APP=/ctx/backend; \
    elif [ -f /ctx/pyproject.toml ]; then APP=/ctx; \
    else echo "ERROR: no backend/pyproject.toml in build context"; ls -la /ctx; exit 1; fi; \
    cp "$APP/pyproject.toml" .; \
    if [ -f "$APP/README.md" ]; then cp "$APP/README.md" .; fi; \
    cp -r "$APP/src" ./src; \
    pip install --no-cache-dir --no-compile .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn citationpulse.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips \"*\""]

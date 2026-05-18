FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --no-compile .

EXPOSE 8000

# Trust proxy headers from Railway's edge (default uvicorn allow-list is 127.0.0.1 only).
CMD ["sh", "-c", "uvicorn citationpulse.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips \"*\""]

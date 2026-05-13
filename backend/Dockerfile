FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy from repo root → backend/ subfolder
COPY backend/pyproject.toml backend/README.md ./
COPY backend/src ./src

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn citationpulse.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

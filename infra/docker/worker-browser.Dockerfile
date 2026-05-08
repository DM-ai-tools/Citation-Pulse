FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy
WORKDIR /app
RUN pip install --no-cache-dir pip setuptools wheel
COPY apps/api/pyproject.toml apps/api/README.md ./
COPY apps/api/src ./src
RUN pip install --no-cache-dir -e .
CMD ["celery", "-A", "citationpulse.celery_app", "worker", "-Q", "browser,default", "-l", "info"]

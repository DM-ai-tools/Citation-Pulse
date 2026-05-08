FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir pip setuptools wheel
COPY apps/api/pyproject.toml apps/api/README.md ./
COPY apps/api/src ./src
RUN pip install --no-cache-dir -e .
EXPOSE 8000
CMD ["uvicorn", "citationpulse.main:app", "--host", "0.0.0.0", "--port", "8000"]

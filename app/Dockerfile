FROM python:3.11-slim AS builder

RUN pip install --user pipx && \
    pipx install poetry

WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-dev

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app

FROM app AS app

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM app AS worker

EXPOSE 8001
CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info"]
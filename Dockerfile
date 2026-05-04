FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash lex

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY data ./data

RUN pip install --upgrade pip \
    && pip install . \
    && chmod +x /app/scripts/ingest_sample.py

USER lex
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "lexorchestrator_au.main:app", "--host", "0.0.0.0", "--port", "8000"]

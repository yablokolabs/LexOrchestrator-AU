# ---------- builder ----------
FROM python:3.12.8-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN pip install --upgrade pip \
    && pip install --prefix=/install .

COPY src ./src
RUN pip install --prefix=/install --no-deps .

# ---------- runtime ----------
FROM python:3.12.8-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --shell /bin/bash lex

COPY --from=builder /install /usr/local
COPY scripts ./scripts
COPY data ./data

USER lex
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "lexorchestrator_au.main:app", "--host", "0.0.0.0", "--port", "8000"]

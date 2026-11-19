# Immagine unica: API + web nello stesso processo (SPEC §8). Contesto di build: radice del repo.
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Layer di cache: solo le dipendenze esterne, invalidato solo da lock e pyproject.
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/web/pyproject.toml apps/web/pyproject.toml
COPY packages/core/pyproject.toml packages/core/pyproject.toml
RUN uv sync --frozen --no-dev --no-install-workspace --package spesometro-api

# Poi i pacchetti del workspace, non editabili: lo stage finale porta solo la .venv.
COPY apps apps
COPY packages packages
RUN uv sync --frozen --no-dev --no-editable --package spesometro-api

FROM python:3.13-slim
RUN useradd --create-home --uid 1000 app
WORKDIR /home/app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    WEB_CONCURRENCY=1
USER app
# PORT arriva dall'ambiente (Railway lo inietta); 1 worker uvicorn.
CMD ["python", "-m", "spesometro_api"]

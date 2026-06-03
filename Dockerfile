# ═══════════════════════════════════════════════════════════════════════════════
# M-18 FIX: Multi-stage build
#   Stage 1 (builder): compiladores + build-essential + git → constrói wheels
#   Stage 2 (runtime): apenas libpq5 + curl → imagem slim sem ferramentas de dev
# ═══════════════════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.14-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements-core.txt requirements.txt ./

# Compilar todas as dependências como wheels (offline install no stage runtime)
RUN pip wheel --no-cache-dir --timeout 300 --retries 5 \
    -r requirements-core.txt \
    -r requirements.txt \
    --wheel-dir /build/wheels

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.14-slim AS runtime

LABEL org.opencontainers.image.title="used-cars-ml API"
LABEL org.opencontainers.image.description="API + ML pipeline para análise de veículos usados"

# Apenas dependências de runtime (sem build-essential, git, compiladores)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Instalar wheels pré-compilados (rápido, sem acesso à internet no runtime)
COPY --from=builder /build/wheels /tmp/wheels
COPY requirements-core.txt requirements.txt ./
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels \
    -r requirements-core.txt \
    -r requirements.txt \
    && rm -rf /tmp/wheels

# Copiar código-fonte
COPY . .

# H-07 FIX: usuário não-privilegiado
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && mkdir -p logs data/raw data/processed models \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000 8501

# H-06 FIX: sem DB_PASSWORD baked na imagem — injetar em runtime
# H-18 FIX: API_RELOAD=false por default
ENV DB_HOST=db \
    DB_PORT=5432 \
    DB_NAME=used_cars \
    DB_USER=postgres \
    REDIS_HOST=redis \
    REDIS_PORT=6379 \
    REDIS_DB=0 \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    API_WORKERS=2 \
    API_RELOAD=false \
    DASHBOARD_PORT=8501 \
    LOG_LEVEL=INFO \
    LOG_FILE=logs/app.log \
    CACHE_TTL=3600 \
    BATCH_SIZE=1000 \
    MAX_WORKERS=4

# H-18 FIX: sem --reload
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

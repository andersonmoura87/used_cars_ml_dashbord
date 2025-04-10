# Use uma imagem base do Python
FROM python:3.8-slim

# Definir variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de requisitos
COPY requirements.txt requirements-dev.txt ./

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-dev.txt

# Copiar o código fonte
COPY . .

# Criar diretórios necessários
RUN mkdir -p logs data/raw data/processed

# Expor portas
EXPOSE 8000 8501

# Definir variáveis de ambiente padrão
ENV DB_HOST=db \
    DB_PORT=5432 \
    DB_NAME=used_cars \
    DB_USER=postgres \
    DB_PASSWORD=postgres \
    REDIS_HOST=redis \
    REDIS_PORT=6379 \
    REDIS_DB=0 \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    API_WORKERS=4 \
    API_RELOAD=true \
    DASHBOARD_PORT=8501 \
    LOG_LEVEL=INFO \
    LOG_FILE=logs/app.log \
    CACHE_TTL=3600 \
    BATCH_SIZE=1000 \
    MAX_WORKERS=4

# Comando padrão
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 
FROM python:3.11-slim

LABEL maintainer="used-cars-ml"
LABEL description="MLflow Tracking Server with PostgreSQL backend"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    mlflow==2.10.2 \
    psycopg2-binary==2.9.9 \
    boto3==1.34.0

# H-07 FIX: usuário não-privilegiado
RUN groupadd -r mlflow && useradd -r -g mlflow mlflow \
    && mkdir -p /mlflow/artifacts \
    && chown -R mlflow:mlflow /mlflow

USER mlflow

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:5000/health || exit 1

ENTRYPOINT ["mlflow", "server"]
CMD [ \
    "--backend-store-uri", "sqlite:///mlflow/mlflow.db", \
    "--default-artifact-root", "/mlflow/artifacts", \
    "--host", "0.0.0.0", \
    "--port", "5000" \
]

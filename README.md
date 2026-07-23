# Used Cars ML Dashboard

Pipeline de **DataOps/MLOps** + API FastAPI + dashboard Streamlit para análise
e precificação de veículos usados.

## Stack

- **Python ≥ 3.11**
- FastAPI · Streamlit (`dashboard/`) · XGBoost · MLflow · Great Expectations
- PostgreSQL + Redis · Docker Compose (perfis `monitoring`, `lineage`)
- CI/CD: GitHub Actions (CI, staging smoke, retrain, promote, data-pipeline, CD)

## Início rápido

```bash
cp .env.example .env          # preencha secrets — ver docs/SECRETS.md
pip install -r requirements.txt
pip install -r requirements-dev.txt

docker compose up -d db redis mlflow

python -m src.etl.run_pipeline          # ETL canônico
uvicorn src.api.main:app --reload --port 8000
streamlit run dashboard/Home.py
```

```bash
python scripts/check_secrets.py --environment development --scope etl
pytest tests/ --ignore=tests/smoke -q
```

## Documentação

| Doc | Conteúdo |
|-----|----------|
| [docs/ETL.md](docs/ETL.md) | Pipeline ETL canônico |
| [docs/SECRETS.md](docs/SECRETS.md) | Secrets GitHub / .env |
| [docs/SPRINT4.md](docs/SPRINT4.md) | Backlog Sprint 4 |
| [docs/runbooks/deploy-rollback.md](docs/runbooks/deploy-rollback.md) | CD e rollback |
| [docs/dax_measures.md](docs/dax_measures.md) | Medidas DAX (Power BI) |
| [data/README.md](data/README.md) | Camada medallion |
| [tests/README.md](tests/README.md) | Como rodar testes |
| [SECURITY.md](SECURITY.md) | Política de segurança |

## Funcionalidades

1. **Análise de Mercado** — métricas, distribuição de preços, outliers
2. **Modelo de preços** — XGBoost + MLflow registry + champion/challenger
3. **API** — `/api/v1/cars`, financing, analytics (`X-API-Key`)
4. **Observabilidade** — Prometheus/Grafana, OpenLineage, alertas Slack
5. **Qualidade** — Great Expectations + quality trend

## Estrutura

```
src/api|etl|models|database   # código principal
dashboard/                    # Streamlit multipage
scripts/                      # CLIs MLOps
tests/unit|smoke              # testes
data/raw|processed|quality    # medallion
docs/                         # ETL, SECRETS, runbooks
.github/workflows/            # CI/CD
docker-compose*.yml
```

## Deploy

1. Tag `v*` dispara CD
2. Staging build + smoke (`SMOKE_STRICT`)
3. Verifica modelo MLflow em Production
4. Deploy SSH por imagem GHCR `sha-<commit>`
5. Health fail → rollback (ver runbook)

## Contribuição

PRs preferidos. Siga `docs/SPRINT4.md` para o backlog atual.

## Licença

MIT — veja `LICENSE`.

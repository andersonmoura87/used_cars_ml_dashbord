# Secrets Checklist — Used Cars ML

Configure em **GitHub → Settings → Secrets and variables → Actions**.
Localmente: copie `.env.example` → `.env` e preencha.

```bash
python scripts/check_secrets.py --environment production --scope etl
python scripts/check_secrets.py --environment production --scope api,cd
python scripts/check_secrets.py --checklist
```

## Escopos

| Scope | Quando | Secrets |
|-------|--------|---------|
| `etl` | `data-pipeline.yml` deploy | `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME` |
| `api` | staging / production API | `API_KEY`, `REDIS_PASSWORD` |
| `cd` | `cd.yml` deploy SSH | `SSH_HOST`, `SSH_USERNAME`, `SSH_PRIVATE_KEY` |
| optional | recomendados | `SLACK_WEBHOOK`, `MLFLOW_*`, `GRAFANA_PASSWORD`, `OPENLINEAGE_URL` |

## Valores proibidos (staging/production)

- `DB_PASSWORD`: `postgres`, `password`, `changeme`, `admin`
- `API_KEY`: `changeme`, `test`, `ci-test-api-key`
- `REDIS_PASSWORD`: `redis`, `password`
- `GRAFANA_PASSWORD`: `admin`, `password`

## Geração

```bash
openssl rand -hex 32
```

Ver também: `docs/ETL.md` (pipeline canônico).

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
| `etl` | `data-pipeline.yml` + CD migrations | `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME` |
| `api` | staging / production API + CD | `API_KEY`, `REDIS_PASSWORD` |
| `cd` | `cd.yml` deploy SSH | `SSH_HOST`, `SSH_USERNAME`, `SSH_PRIVATE_KEY` |
| staging | `staging.yml` via CD | `STAGING_API_KEY`, `DB_PASSWORD_STAGING`, `REDIS_PASSWORD_STAGING` |
| optional | recomendados | `SLACK_WEBHOOK`, `MLFLOW_*`, `GRAFANA_PASSWORD`, `OPENLINEAGE_URL` |

## Gates no CI/CD (UCM-33)

| Workflow | Comando |
|----------|---------|
| `data-pipeline.yml` (deploy) | `--scope etl` |
| `cd.yml` (deploy) | `--scope etl,api,cd` |

## Valores proibidos (staging/production)

- `DB_PASSWORD`: `postgres`, `password`, `changeme`, `admin`
- `API_KEY`: `changeme`, `test`, `ci-test-api-key`
- `REDIS_PASSWORD`: `redis`, `password`
- `GRAFANA_PASSWORD`: `admin`, `password`

## Geração

```bash
openssl rand -hex 32
```

Ver: `docs/ETL.md` · `docs/runbooks/deploy-rollback.md`

# Runbook — Deploy produção e rollback (UCM-34)

## Fluxo CD (`cd.yml`)

```
tag v* 
  → staging-gate (build GHCR + compose staging + smoke STRICT)
  → check-model (MLflow Production)
  → validate secrets (api + cd)
  → migrate DB
  → SSH deploy imagem sha-<commit>
  → health /health
  → Slack notify
```

Smoke failure **bloqueia** produção (job `staging-gate` falha → `deploy` não roda).

## Pré-requisitos (secrets)

Ver `docs/SECRETS.md`. Escopos usados no CD:

```bash
python scripts/check_secrets.py --environment production --scope api,cd
```

| Secret | Uso |
|--------|-----|
| `STAGING_API_KEY` | Smoke staging |
| `DB_PASSWORD_STAGING` / `REDIS_PASSWORD_STAGING` | Compose staging (opcional; CI gera se ausente) |
| `DB_*` | Migrations produção |
| `SSH_HOST` / `SSH_USERNAME` / `SSH_PRIVATE_KEY` / `SSH_PORT` | Deploy |
| `MLFLOW_TRACKING_URI` | Gate de modelo (opcional se vazio = skip) |
| `SLACK_WEBHOOK` | Notificações |

## Rollback automático

Se `curl /health` falhar após `docker compose up`:

1. `docker compose down`
2. Reinicia container anterior (`PREV_ID`) **ou**
3. Pull da tag anterior conhecida: `used-cars-ml:sha-<previous_sha>`

## Rollback manual

No servidor (`/opt/used-cars-analysis`):

```bash
# Listar imagens recentes
docker images ghcr.io/<owner>/used-cars-ml

# Voltar para SHA anterior
export DOCKER_IMAGE=ghcr.io/<owner>/used-cars-ml:sha-<PREVIOUS_SHA>
docker pull "$DOCKER_IMAGE"
DOCKER_IMAGE="$DOCKER_IMAGE" docker compose up -d --remove-orphans
curl -sf http://localhost:8000/health
```

Ou via tag Git anterior:

```bash
git fetch --tags
# redeploy da tag estável anterior (re-dispara CD) — ou
# use a imagem sha- do commit da tag
```

## Verificação pós-deploy

```bash
curl -sf http://localhost:8000/health
curl -sf -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/cars?limit=1
curl -sf http://localhost:8000/metrics | head
```

## Contatos

- Falha de smoke: logs do job Staging Gate + `docker compose logs`
- Falha de secrets: `docs/SECRETS.md`
- ETL: `docs/ETL.md`

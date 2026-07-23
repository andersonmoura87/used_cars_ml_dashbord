## Estrutura

```
tests/
├── unit/               # Testes unitários (sem I/O real)
│   ├── test_db.py          # unitários mockados + integration opcional
│   ├── test_extract.py     # ETL extract
│   ├── test_transform.py   # ETL transform
│   ├── test_load.py        # ETL load (mocks SQLAlchemy)
│   ├── test_run_pipeline.py
│   └── test_cleaning.py    # utils.clean_prices
├── integration/        # (futuro)
├── smoke/              # Smoke pós-deploy (API viva)
│   ├── conftest.py
│   └── test_api_smoke.py
├── test_ge_validation.py
├── test_lineage.py
├── test_mlflow_integration.py
├── test_check_drift.py
├── test_compare_models.py
├── test_model_card.py
├── test_notify_etl.py
├── test_quality_trend.py
├── test_telemetry.py
└── test_check_secrets.py
```

## Executar

```bash
# Todos (exceto smoke)
pytest

# ETL core + DB unitários
pytest tests/unit/ -q

# Integração DB (requer PostgreSQL + INTEGRATION_DB=1)
INTEGRATION_DB=1 pytest tests/unit/test_db.py -m integration -q

# Smoke (requer API)
pytest tests/smoke/
```

Pipeline canônico: `docs/ETL.md` · Secrets: `docs/SECRETS.md` · Deploy: `docs/runbooks/deploy-rollback.md`

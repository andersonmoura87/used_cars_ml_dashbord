## Estrutura

```
tests/
├── unit/               # Testes unitários (sem I/O real)
│   ├── test_cleaning.py
│   ├── test_db.py          # skipped — requer DB populado
│   ├── test_extract.py     # ETL extract
│   ├── test_transform.py   # ETL transform
│   ├── test_load.py        # ETL load (mocks SQLAlchemy)
│   └── test_run_pipeline.py
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

# ETL core
pytest tests/unit/test_extract.py tests/unit/test_transform.py \
       tests/unit/test_load.py tests/unit/test_run_pipeline.py -q

# Smoke (requer API)
pytest tests/smoke/
```

Pipeline canônico: `docs/ETL.md` · Secrets: `docs/SECRETS.md`

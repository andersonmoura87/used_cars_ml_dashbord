# Pipeline ETL — Fonte Canônica (UCM-27)

## Entrypoint de produção

```bash
python -m src.etl.run_pipeline
# ou, após pip install -e .
run-etl
```

Fluxo:

```
extract_data()
  → validate_raw()          # Great Expectations (não-bloqueante)
  → transform_data()
  → validate_clean()        # Great Expectations (bloqueante)
  → load_data()             # ORM SQLAlchemy → PostgreSQL
  → OpenLineage events      # se OPENLINEAGE_URL configurado
  → record_etl_run()        # métrica Prometheus (se disponível)
```

CI: `.github/workflows/data-pipeline.yml` chama **apenas** este pipeline e
falha o job se o exit code ≠ 0. Triggers incluem `src/etl/**`.

## Status dos paths paralelos (UCM-27)

| Caminho | Status | Comportamento |
|---------|--------|---------------|
| `src/etl/run_pipeline.py` | **Canônico** | Produção + CI |
| `scripts/run_etl.py` | Wrapper | DeprecationWarning → `run_pipeline` |
| `scripts/pipeline/cars_etl.py` | **Stub** | DeprecationWarning → `run_pipeline` (sem Prefect/DataCleaner) |
| `src/etl/process_data.py` | Deprecated | Warning; remoção em UCM-28 |
| `src/etl/process_sample.py` | Deprecated | Warning; remoção em UCM-28 |
| `src/etl/load_data.py` | Deprecated | Warning; use `src.etl.load` |
| `src/etl/validate_data.py` | Deprecated | Warning; use `ge_validation` |
| `scripts/cleaning/data_cleaner.py` | Deprecated | Warning; remoção em UCM-28 |
| `scripts/load_to_postgres.py` | Deprecated | Warning; remoção em UCM-28 |

## Por que um só?

- Schemas diferentes entre `PostgresLoader.to_sql` e ORM (`Car` / `MarketStats`)
- GE + lineage + telemetria só no canônico
- Um contrato de metadados (`logs/metadata/pipeline_*.json`)

## Testes

```bash
pytest tests/unit/test_extract.py tests/unit/test_transform.py \
       tests/unit/test_load.py tests/unit/test_run_pipeline.py \
       tests/test_pipeline.py -q
```

## Próximos (Sprint 4)

- **UCM-28** — deletar módulos deprecated
- **UCM-29** — done parcialmente (test_pipeline realinhado)
- **UCM-37** — ADR Prefect (manter thin experimental vs remover `requirements-etl.txt`)

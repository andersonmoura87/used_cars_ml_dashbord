# Pipeline ETL — Fonte Canônica

## Entrypoint de produção

```bash
python -m src.etl.run_pipeline
```

Ou via CLI (wrapper):

```bash
run-etl
# equivalente a: python scripts/run_etl.py
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

CI: `.github/workflows/data-pipeline.yml` chama **apenas** este pipeline.
Falha do ETL falha o job (exit ≠ 0).

## Pipelines deprecados

| Caminho | Status | Motivo |
|---------|--------|--------|
| `scripts/run_etl.py` | **Wrapper** → `src.etl.run_pipeline` | Antes tinha API quebrada (`transform_data` retorna 4-tuple) |
| `scripts/pipeline/cars_etl.py` | **Deprecated** (Prefect) | Requer `requirements-etl.txt`; conflito starlette; não usado no CI |
| `src/etl/process_data.py` | Legacy | Transformação CSV→CSV sem DB/GE |
| `src/etl/process_sample.py` | Legacy | Sample helper |
| `src/etl/load_data.py` | Legacy | Load SQL paralelo ao ORM `load.py` |
| `src/etl/validate_data.py` | Legacy | Pré-GE; use `ge_validation.py` |

## Por que um só?

- Schemas diferentes entre Prefect (`PostgresLoader.to_sql`) e ORM (`Car` / `MarketStats`)
- GE + lineage + telemetria só no canônico
- Um contrato de metadados (`logs/metadata/pipeline_*.json`)

## Testes

```bash
pytest tests/unit/test_extract.py tests/unit/test_transform.py \
       tests/unit/test_load.py tests/unit/test_run_pipeline.py -q
```

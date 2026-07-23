# Pipeline ETL — Fonte Canônica

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

## Módulos (UCM-28)

| Caminho | Papel |
|---------|--------|
| `src/etl/run_pipeline.py` | Entrypoint canônico (produção + CI) |
| `src/etl/extract.py` | Extração |
| `src/etl/transform.py` | Transformação / limpeza |
| `src/etl/load.py` | Carga ORM → PostgreSQL |
| `src/etl/ge_validation.py` | Great Expectations |
| `src/etl/lineage.py` | OpenLineage (opcional) |

Paths paralelos (`process_data`, `DataCleaner`, `PostgresLoader`, stub Prefect)
foram **removidos** em UCM-28. Decisão sobre `requirements-etl.txt` / Prefect: **UCM-37**.

## Por que um só?

- Schemas unificados via ORM (`Car` / `MarketStats`)
- GE + lineage + telemetria só no canônico
- Um contrato de metadados (`logs/metadata/pipeline_*.json`)

## Testes

```bash
pytest tests/unit/test_extract.py tests/unit/test_transform.py \
       tests/unit/test_load.py tests/unit/test_run_pipeline.py -q
```

## Próximos (Sprint 4)

- **UCM-37** — ADR Prefect (manter thin experimental vs remover `requirements-etl.txt`)
- **UCM-31** — cobertura ≥70% módulos críticos remanescentes

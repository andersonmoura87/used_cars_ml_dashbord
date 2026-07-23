## Camada de Dados — Estrutura Medallion

```
data/
├── raw/            # Dados brutos (gitignored: *.csv, *.parquet, *.json)
│                   # Populado manualmente ou por ingestão externa
│
├── processed/      # ABT final pronta para treino (gitignored: *.csv, *.parquet)
│                   # Populado por: src/etl/transform.py
│
├── interim/        # Transformações intermediárias (gitignored)
│
├── quality/        # Relatórios GE + quality_history.jsonl + quality_trend.json
│                   # Gerado por: src/etl/ge_validation.py + scripts/quality_trend.py
│
├── reference/      # Datasets de referência para drift detection
│
├── cleansed/       # Dados limpos em Parquet (legado — usar processed/)
│
├── analysis/       # Outputs de análise exploratória
│
├── export/         # Exports para Power BI
│
└── predictions/    # Previsões de mercado (listing_forecast.csv)
```

## Pipeline canônico

```bash
# Única fonte de verdade em produção / CI
python -m src.etl.run_pipeline

# Wrapper CLI (emite DeprecationWarning e delega ao canônico)
python scripts/run_etl.py
```

Ver `docs/ETL.md` para pipelines deprecados (Prefect, load_data legado, etc.).

## Notas

- Arquivos `*.csv` e `*.parquet` em `raw/` e `processed/` **não são versionados**
- Apenas arquivos `.gitkeep` e relatórios JSON em `quality/` são comitados
- Secrets: `docs/SECRETS.md` + `python scripts/check_secrets.py --scope etl`

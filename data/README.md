# Camada de Dados — Estrutura Medallion

```
data/
├── raw/            # Dados brutos (gitignored: *.csv, *.parquet, *.json)
│                   # Populado por: scripts/run_etl.py → src/etl/extract.py
│
├── processed/      # ABT final pronta para treino (gitignored: *.csv, *.parquet)
│                   # Populado por: src/etl/transform.py
│
├── interim/        # Transformações intermediárias (gitignored)
│
├── quality/        # Relatórios de qualidade de dados (JSON — versionado)
│                   # Gerado por: src/etl/ge_validation.py
│
├── reference/      # Datasets de referência para drift detection (versionado)
│                   # Gerado por: scripts/pipeline/cars_etl.py
│
├── cleansed/       # Dados limpos em Parquet (legado — usar processed/)
│
├── analysis/       # Outputs de análise exploratória
│
├── export/         # Exports para Power BI
│
└── predictions/    # Previsões de mercado (listing_forecast.csv)
```

## Notas

- Arquivos `*.csv` e `*.parquet` em `raw/` e `processed/` **não são versionados**
- Apenas arquivos `.gitkeep` e relatórios JSON em `quality/` são comitados
- Para popular `data/raw/`, execute: `python scripts/run_etl.py`

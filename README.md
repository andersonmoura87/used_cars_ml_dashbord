# Used Cars ML Dashboard

Pipeline de **DataOps/MLOps** + API FastAPI + dashboard Streamlit para análise
e precificação de veículos usados.

## Stack

- **Python ≥ 3.11**
- FastAPI (API), Streamlit (`dashboard/`), XGBoost, MLflow, Great Expectations
- PostgreSQL + Redis · Docker Compose (perfis `monitoring`, `lineage`)
- CI/CD: GitHub Actions (CI, staging smoke, retrain, promote, data-pipeline)

## Início rápido

```bash
cp .env.example .env          # preencha secrets — ver docs/SECRETS.md
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Infra local
docker compose up -d db redis mlflow

# ETL canônico
python -m src.etl.run_pipeline

# API
uvicorn src.api.main:app --reload --port 8000

# Dashboard
streamlit run dashboard/Home.py
```

Validar secrets: `python scripts/check_secrets.py --environment development --scope etl`

## Documentação

| Doc | Conteúdo |
|-----|----------|
| [docs/ETL.md](docs/ETL.md) | Pipeline ETL canônico (UCM-27) |
| [docs/SECRETS.md](docs/SECRETS.md) | Secrets GitHub / .env |
| [docs/SPRINT4.md](docs/SPRINT4.md) | Backlog Sprint 4 (UCM-27+) |
| [data/README.md](data/README.md) | Camada medallion |
| [tests/README.md](tests/README.md) | Como rodar testes |
| [SECURITY.md](SECURITY.md) | Política de segurança |

## Funcionalidades

1. **Análise de Mercado** — métricas, distribuição de preços, outliers
2. **Modelo de preços** — XGBoost + MLflow registry + champion/challenger
3. **API** — `/api/v1/cars`, financing, analytics (auth `X-API-Key`)
4. **Observabilidade** — Prometheus/Grafana, OpenLineage, alertas Slack
5. **Qualidade** — Great Expectations + quality trend

## Medidas DAX Disponíveis

### Medidas de Preço por Ano
```dax
// Preço Médio por Ano
Avg_Price_Year = CALCULATE(AVERAGE('cars'[price]), GROUPBY('cars', 'cars'[year]))

// Preço Mediano por Ano
Median_Price_Year = CALCULATE(PERCENTILE.INC('cars'[price], 0.5), GROUPBY('cars', 'cars'[year]))

// Desvio Padrão dos Preços por Ano
StdDev_Price_Year = CALCULATE(STDEV.P('cars'[price]), GROUPBY('cars', 'cars'[year]))
```

### Medidas de Distribuição
```dax
// Quartis de Preço por Ano
Q1_Price_Year = CALCULATE(PERCENTILE.INC('cars'[price], 0.25), GROUPBY('cars', 'cars'[year]))
Q3_Price_Year = CALCULATE(PERCENTILE.INC('cars'[price], 0.75), GROUPBY('cars', 'cars'[year]))
IQR_Price_Year = [Q3_Price_Year] - [Q1_Price_Year]

// Coeficiente de Variação
CV_Price_Year = DIVIDE([StdDev_Price_Year], [Avg_Price_Year])
```

## Requisitos

- Python **3.11+**
- Dependências em `requirements.txt` (+ `requirements-dev.txt` para testes)

## Instalação

```bash
git clone <repository-url>
cd used_cars_ml_dashbord
cp .env.example .env
pip install -r requirements.txt
```

## Uso

```bash
# Dashboard multipage
streamlit run dashboard/Home.py
# → http://localhost:8501

# API
uvicorn src.api.main:app --port 8000
# → http://localhost:8000/docs
```

## Estrutura do Projeto

```
.
├── src/
│   ├── api/              # FastAPI + telemetry
│   ├── etl/              # Pipeline canônico (extract/transform/load/run_pipeline)
│   ├── models/           # AdvancedPriceModel + MLflow
│   ├── database/         # SQLAlchemy
│   └── utils/
├── dashboard/            # Streamlit multipage (Home + pages/)
├── scripts/              # CLIs MLOps (retrain, promote, drift, notify…)
├── tests/                # unit / smoke / MLOps
├── data/                 # medallion: raw / processed / quality
├── docker/               # prometheus, grafana, mlflow
├── docs/                 # ETL, SECRETS, SPRINT4, model_cards
├── docker-compose.yml
├── docker-compose.staging.yml
└── .github/workflows/
```

## Análises Disponíveis

### Análise Estatística
- Distribuição de preços
  - Medidas de tendência central
  - Medidas de dispersão
- Análises bivariadas
  - Correlações importantes
  - Padrões temporais
- Identificação de outliers
  - Método IQR
  - Impacto nas análises

### Análise de Mercado
- Total de veículos
- Preço médio
- Quilometragem média
- Ano médio
- Distribuição de preços
- Preço médio por fabricante
- Modelo preditivo de preços

### Previsão de Vendas
- Seleção de período de forecast
- Análise por fabricante
- Gráfico de tendências
- Métricas de crescimento

### Recomendações de Compra
- Margem de lucro alvo
- Investimento máximo
- Ano mínimo
- Quilometragem máxima
- Top 10 oportunidades
- Distribuição de margens

## Contribuição

Sinta-se à vontade para contribuir com melhorias através de pull requests.

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo LICENSE para detalhes. 
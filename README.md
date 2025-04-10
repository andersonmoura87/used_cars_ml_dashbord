# Dashboard de Análise de Mercado de Carros Usados

Este dashboard interativo permite analisar dados do mercado de carros usados, incluindo análises estatísticas avançadas, previsões de preços, análise de tendências e recomendações de compra para revenda.

## Funcionalidades

1. **Análise de Mercado**
   - Visualização de métricas principais (total de veículos, preço médio, etc.)
   - Distribuição de preços com análise estatística completa
   - Preço médio por fabricante
   - Modelo preditivo de preços usando XGBoost
   - Análise de outliers e impacto no mercado

2. **Análises Estatísticas**
   - **Distribuição de Preços**
     - Medidas de tendência central (média, mediana, moda)
     - Medidas de dispersão (desvio padrão, variância, IQR)
     - Análise de assimetria e curtose
   
   - **Análises Bivariadas**
     - Correlações entre variáveis chave
     - Padrões temporais
     - Relações preço-quilometragem
   
   - **Identificação de Outliers**
     - Método IQR para detecção
     - Análise de impacto nos resultados
     - Tratamento e filtragem

3. **Previsão de Vendas**
   - Forecast de vendas por fabricante
   - Análise de tendências
   - Intervalos de confiança
   - Métricas de crescimento

4. **Recomendações de Compra**
   - Identificação de oportunidades de revenda
   - Análise de margens de lucro
   - Filtros personalizáveis
   - Top 10 oportunidades

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

- Python 3.8+
- Dependências listadas em `requirements.txt`

## Instalação

1. Clone o repositório:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Uso

1. Execute o dashboard:
```bash
streamlit run scripts/market_dashboard.py
```

2. Acesse o dashboard no navegador (geralmente em http://localhost:8501)

## Estrutura do Projeto

```
.
├── data/
│   ├── raw/
│   │   └── cars.csv
│   └── processed/
│       └── cars_abt.csv
├── scripts/
│   ├── analysis/
│   │   ├── descriptive_analysis.py
│   │   ├── statistical_analysis.py
│   │   └── advanced_analytics.py
│   ├── etl/
│   │   └── transform.py
│   └── market_dashboard.py
├── requirements.txt
└── README.md
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
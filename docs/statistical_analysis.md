# Documentação Técnica - Análises Estatísticas

## Visão Geral

Este documento detalha as análises estatísticas implementadas no projeto, incluindo metodologias, fórmulas e interpretações.

## 1. Distribuição de Preços

### 1.1 Medidas de Tendência Central

- **Média**: \[ \bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i \]
- **Mediana**: Valor central quando os dados estão ordenados
- **Moda**: Valor mais frequente na distribuição

### 1.2 Medidas de Dispersão

- **Desvio Padrão**: \[ s = \sqrt{\frac{1}{n-1}\sum_{i=1}^{n}(x_i - \bar{x})^2} \]
- **Variância**: \[ s^2 = \frac{1}{n-1}\sum_{i=1}^{n}(x_i - \bar{x})^2 \]
- **IQR (Intervalo Interquartil)**: \[ IQR = Q3 - Q1 \]

### 1.3 Implementação

```python
def price_distribution(df):
    stats = {
        'mean': float(df['price'].mean()),
        'median': float(df['price'].median()),
        'std': float(df['price'].std()),
        'skewness': float(df['price'].skew()),
        'kurtosis': float(df['price'].kurtosis())
    }
    return stats
```

## 2. Análises Bivariadas

### 2.1 Correlações Importantes

- Preço vs. Ano
- Preço vs. Quilometragem
- Preço vs. Condição

### 2.2 Padrões Temporais

- Análise de séries temporais
- Decomposição de tendências
- Sazonalidade

### 2.3 Implementação

```python
def analyze_correlations(df):
    correlations = {
        'price_year': df[['price', 'year']].corr().iloc[0,1],
        'price_mileage': df[['price', 'odometer']].corr().iloc[0,1]
    }
    return correlations
```

## 3. Identificação de Outliers

### 3.1 Método IQR

1. Calcular Q1 (primeiro quartil) e Q3 (terceiro quartil)
2. Calcular IQR = Q3 - Q1
3. Definir limites:
   - Limite inferior = Q1 - 1.5 * IQR
   - Limite superior = Q3 + 1.5 * IQR

### 3.2 Implementação

```python
def detect_outliers(df):
    Q1 = df['price'].quantile(0.25)
    Q3 = df['price'].quantile(0.75)
    IQR = Q3 - Q1
    
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    outliers = df[
        (df['price'] < lower_bound) |
        (df['price'] > upper_bound)
    ]
    return outliers
```

## 4. Medidas DAX

### 4.1 Medidas de Preço por Ano

```dax
// Preço Médio por Ano
Avg_Price_Year = 
CALCULATE(
    AVERAGE('cars'[price]),
    GROUPBY('cars', 'cars'[year])
)

// Preço Mediano por Ano
Median_Price_Year = 
CALCULATE(
    PERCENTILE.INC('cars'[price], 0.5),
    GROUPBY('cars', 'cars'[year])
)
```

### 4.2 Medidas de Distribuição

```dax
// Quartis de Preço por Ano
Q1_Price_Year = 
CALCULATE(
    PERCENTILE.INC('cars'[price], 0.25),
    GROUPBY('cars', 'cars'[year])
)

Q3_Price_Year = 
CALCULATE(
    PERCENTILE.INC('cars'[price], 0.75),
    GROUPBY('cars', 'cars'[year])
)

// IQR por Ano
IQR_Price_Year = [Q3_Price_Year] - [Q1_Price_Year]
```

## 5. Visualizações

### 5.1 Gráficos de Distribuição
- Histogramas
- Box plots
- Violin plots
- Q-Q plots

### 5.2 Gráficos de Correlação
- Scatter plots
- Heat maps
- Pair plots

### 5.3 Gráficos Temporais
- Line plots
- Area charts
- Decomposition plots

## 6. Interpretação dos Resultados

### 6.1 Distribuição de Preços
- Assimetria positiva indica concentração em preços mais baixos
- Outliers superiores representam veículos de luxo/coleção
- IQR fornece range de preços "típico" do mercado

### 6.2 Correlações
- Correlação negativa entre preço e quilometragem
- Correlação positiva entre preço e ano
- Variações sazonais nos preços médios

### 6.3 Outliers
- Impacto na média vs mediana
- Segmentação do mercado
- Estratégias de precificação

## 7. Uso das Análises

### 7.1 Precificação
- Definição de faixas de preço por segmento
- Ajuste por sazonalidade
- Consideração de outliers

### 7.2 Estratégia de Mercado
- Identificação de nichos
- Otimização de estoque
- Previsão de tendências

### 7.3 Tomada de Decisão
- Compra e venda
- Definição de margens
- Avaliação de oportunidades 
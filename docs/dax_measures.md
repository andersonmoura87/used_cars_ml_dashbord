# Documentação das Medidas DAX

## Visão Geral

Este documento detalha todas as medidas DAX implementadas no projeto, incluindo sua finalidade, fórmulas e uso recomendado.

## 1. Medidas de Preço por Ano

### 1.1 Preço Médio por Ano
```dax
Avg_Price_Year = 
CALCULATE(
    AVERAGE('cars'[price]),
    GROUPBY('cars', 'cars'[year])
)
```
**Uso**: Calcula o preço médio dos veículos para cada ano de fabricação.
**Contexto**: Útil para análise de tendências de preço ao longo do tempo.

### 1.2 Preço Mediano por Ano
```dax
Median_Price_Year = 
CALCULATE(
    PERCENTILE.INC('cars'[price], 0.5),
    GROUPBY('cars', 'cars'[year])
)
```
**Uso**: Calcula o preço mediano dos veículos para cada ano.
**Contexto**: Mais robusto que a média para dados com outliers.

### 1.3 Desvio Padrão dos Preços por Ano
```dax
StdDev_Price_Year = 
CALCULATE(
    STDEV.P('cars'[price]),
    GROUPBY('cars', 'cars'[year])
)
```
**Uso**: Calcula a dispersão dos preços em cada ano.
**Contexto**: Indica a variabilidade dos preços dentro do mesmo ano.

## 2. Medidas de Distribuição

### 2.1 Quartis de Preço por Ano
```dax
// Primeiro Quartil
Q1_Price_Year = 
CALCULATE(
    PERCENTILE.INC('cars'[price], 0.25),
    GROUPBY('cars', 'cars'[year])
)

// Terceiro Quartil
Q3_Price_Year = 
CALCULATE(
    PERCENTILE.INC('cars'[price], 0.75),
    GROUPBY('cars', 'cars'[year])
)

// IQR (Intervalo Interquartil)
IQR_Price_Year = [Q3_Price_Year] - [Q1_Price_Year]
```
**Uso**: Calcula os quartis e o IQR para análise da distribuição.
**Contexto**: Fundamental para identificação de outliers.

### 2.2 Coeficiente de Variação
```dax
CV_Price_Year = 
DIVIDE(
    [StdDev_Price_Year],
    [Avg_Price_Year]
)
```
**Uso**: Mede a dispersão relativa dos preços.
**Contexto**: Permite comparar a variabilidade entre diferentes anos.

## 3. Medidas de Contagem

### 3.1 Contagem de Veículos por Ano
```dax
Count_Cars_Year = 
CALCULATE(
    COUNTROWS('cars'),
    GROUPBY('cars', 'cars'[year])
)
```
**Uso**: Conta o número de veículos por ano de fabricação.
**Contexto**: Importante para análise de volume e representatividade.

## 4. Medidas de Amplitude

### 4.1 Amplitude de Preços por Ano
```dax
// Preço Mínimo
Min_Price_Year = 
CALCULATE(
    MIN('cars'[price]),
    GROUPBY('cars', 'cars'[year])
)

// Preço Máximo
Max_Price_Year = 
CALCULATE(
    MAX('cars'[price]),
    GROUPBY('cars', 'cars'[year])
)

// Amplitude
Price_Range_Year = [Max_Price_Year] - [Min_Price_Year]
```
**Uso**: Calcula a diferença entre o maior e menor preço por ano.
**Contexto**: Útil para entender a faixa de preços em cada ano.

## 5. Uso em Visualizações

### 5.1 Box Plot por Ano
```dax
// Elementos necessários:
- [Q1_Price_Year]
- [Median_Price_Year]
- [Q3_Price_Year]
- [Min_Price_Year]
- [Max_Price_Year]
```
**Uso**: Criar box plots para visualizar a distribuição dos preços.

### 5.2 Gráfico de Dispersão
```dax
// Elementos necessários:
- [Avg_Price_Year]
- [Count_Cars_Year] (para tamanho dos pontos)
```
**Uso**: Visualizar tendências e padrões nos preços ao longo dos anos.

## 6. Boas Práticas

1. **Filtragem de Dados**:
   - Sempre considerar filtros ativos no contexto
   - Verificar impacto de outliers nas medidas

2. **Performance**:
   - Usar GROUPBY para pré-agregações
   - Evitar cálculos redundantes

3. **Manutenção**:
   - Documentar alterações nas medidas
   - Testar impacto em visualizações existentes

## 7. Exemplos de Uso

### 7.1 Análise de Tendências
```dax
// Variação Percentual Ano a Ano
Price_YoY_Change = 
DIVIDE(
    [Avg_Price_Year] - CALCULATE([Avg_Price_Year], PREVIOUSYEAR('Calendar'[Date])),
    CALCULATE([Avg_Price_Year], PREVIOUSYEAR('Calendar'[Date]))
)
```

### 7.2 Análise de Outliers
```dax
// Flag para Outliers
Is_Price_Outlier = 
IF(
    'cars'[price] < [Q1_Price_Year] - 1.5 * [IQR_Price_Year] ||
    'cars'[price] > [Q3_Price_Year] + 1.5 * [IQR_Price_Year],
    "Outlier",
    "Normal"
)
```

## 8. Troubleshooting

1. **Valores Nulos**:
   - Usar IFERROR para tratamento
   - Verificar divisão por zero

2. **Contexto de Filtro**:
   - Atenção ao uso de CALCULATE
   - Verificar propagação de filtros

3. **Performance**:
   - Monitorar tempo de cálculo
   - Otimizar medidas complexas 
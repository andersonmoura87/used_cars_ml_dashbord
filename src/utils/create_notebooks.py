import nbformat as nbf
import os

def create_data_cleaning_notebook():
    nb = nbf.v4.new_notebook()
    
    cells = [
        nbf.v4.new_markdown_cell("""# Análise de Limpeza de Dados

Este notebook documenta a análise que levou à identificação e correção de problemas nos dados de veículos usados.

## Análise Inicial dos Dados

Primeiro, vamos analisar os dados brutos para identificar possíveis problemas e anomalias."""),
        
        nbf.v4.new_code_cell("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

# Configurar visualização
plt.style.use('seaborn')
sns.set_palette('husl')

# Configurar conexão com o banco
load_dotenv()
engine = create_engine(
    f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
)

# Carregar dados originais
df = pd.read_sql("SELECT * FROM cars", engine)"""),

        nbf.v4.new_markdown_cell("### Análise de Preços"),
        
        nbf.v4.new_code_cell("""# Estatísticas básicas dos preços
print("Estatísticas dos preços:")
print(df['price'].describe())

# Plotar histograma dos preços
plt.figure(figsize=(12, 6))
sns.histplot(df['price'], bins=50)
plt.title('Distribuição dos Preços dos Veículos (Dados Brutos)')
plt.xlabel('Preço ($)')
plt.ylabel('Frequência')
plt.show()

# Identificar preços suspeitos
low_prices = df[df['price'] < 500]
high_prices = df[df['price'] > 1000000]

print("\nExemplos de preços muito baixos (< $500):")
print(low_prices[['manufacturer', 'model', 'year', 'price', 'state']].head())

print("\nExemplos de preços muito altos (> $1,000,000):")
print(high_prices[['manufacturer', 'model', 'year', 'price', 'state']].head())"""),

        nbf.v4.new_markdown_cell("### Análise de Anúncios Suspeitos"),
        
        nbf.v4.new_code_cell("""# Analisar descrições de anúncios com preços baixos
print("Exemplos de descrições de anúncios com preços baixos:")
for idx, row in low_prices.head().iterrows():
    print(f"\n{row['manufacturer']} {row['model']} {row['year']} - ${row['price']}")
    print(f"Descrição: {row['description'][:500]}...")
    print("-" * 80)"""),

        nbf.v4.new_markdown_cell("""## Problemas Identificados

A análise inicial revelou vários problemas nos dados:

1. **Preços Irrealistas**
   - Preços extremamente baixos ($499) para veículos de alto valor
   - Exemplo: BMW 740e com MSRP de $109,305 sendo anunciado por $499
   - Honda Odyssey EX-L 2019 valendo $36,963 sendo anunciado por $499

2. **Anúncios de Financiamento vs Vendas Diretas**
   - Preços anunciados são apenas valores de entrada
   - Não refletem o valor real do veículo
   - São anúncios de "buy here pay here" (BHPH) ou financiamento
   - Muitos não especificam os pagamentos mensais ou taxas de juros

3. **Falta de Transparência**
   - Anúncios focam em atrair com entradas baixas
   - Não revelam o custo total do financiamento
   - Não especificam claramente os termos do financiamento
   - Muitos são anúncios genéricos de "todos aprovados"

4. **Duplicidade de Anúncios**
   - Múltiplos anúncios do mesmo veículo
   - Mesmo anúncio repetido com pequenas variações
   - Anúncios genéricos que se aplicam a múltiplos veículos"""),

        nbf.v4.new_markdown_cell("## Análise dos Registros Removidos"),
        
        nbf.v4.new_code_cell("""# Carregar dados removidos
df_removed = pd.read_sql("SELECT * FROM cars_removed", engine)

print("Estatísticas dos registros removidos:")
print(f"Total de registros removidos: {len(df_removed)}")
print(f"Preço médio dos registros removidos: ${df_removed['price'].mean():,.2f}")
print(f"Mediana dos preços removidos: ${df_removed['price'].median():,.2f}")

# Distribuição por estado
print("\nDistribuição por estado:")
print(df_removed['state'].value_counts().head(10))

# Distribuição por fabricante
print("\nDistribuição por fabricante:")
print(df_removed['manufacturer'].value_counts().head(10))

# Plotar distribuição dos preços removidos
plt.figure(figsize=(12, 6))
sns.histplot(df_removed['price'], bins=50)
plt.title('Distribuição dos Preços dos Veículos Removidos')
plt.xlabel('Preço ($)')
plt.ylabel('Frequência')
plt.show()"""),

        nbf.v4.new_markdown_cell("""## Conclusões

A análise revelou a necessidade de limpar os dados removendo:

1. Registros com preços abaixo de $500 (provavelmente anúncios de financiamento)
2. Registros com preços acima de $1,000,000 (provavelmente erros)
3. Anúncios duplicados
4. Anúncios que são claramente de financiamento

Estas limpezas foram implementadas no script de limpeza e os resultados podem ser vistos no notebook de análise descritiva.""")
    ]
    
    nb.cells = cells
    return nb

def create_descriptive_analysis_notebook():
    nb = nbf.v4.new_notebook()
    
    cells = [
        nbf.v4.new_markdown_cell("""# Análise Descritiva dos Veículos Usados

Este notebook realiza uma análise descritiva dos dados limpos de veículos usados, respondendo às seguintes questões:

1. Qual a distribuição dos preços dos veículos (mediana, média, desvio-padrão)?
2. Qual a relação entre o ano de fabricação e o preço médio dos veículos?
3. Qual a variação da quilometragem média por tipo de combustível e fabricante?
4. Existe alguma correlação significativa entre a quilometragem e o preço dos veículos?
5. Identifique possíveis outliers nos preços utilizando o método do intervalo interquartil (IQR)."""),
        
        nbf.v4.new_code_cell("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

# Configurar visualização
plt.style.use('seaborn')
sns.set_palette('husl')

# Configurar conexão com o banco
load_dotenv()
engine = create_engine(
    f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
)

# Carregar dados
df = pd.read_sql("SELECT * FROM cars_cleaned", engine)"""),
        
        nbf.v4.new_markdown_cell("## 1. Distribuição dos Preços"),
        
        nbf.v4.new_code_cell("""# Estatísticas descritivas
print("Estatísticas dos preços:")
print(df['price'].describe())

# Plotar histograma
plt.figure(figsize=(12, 6))
sns.histplot(df['price'], bins=50)
plt.title('Distribuição dos Preços dos Veículos')
plt.xlabel('Preço ($)')
plt.ylabel('Frequência')
plt.show()"""),

        nbf.v4.new_markdown_cell("## 2. Relação entre Ano e Preço Médio"),
        
        nbf.v4.new_code_cell("""# Calcular preço médio por ano
price_by_year = df.groupby('year')['price'].agg(['mean', 'count']).reset_index()
price_by_year.columns = ['year', 'mean_price', 'count']

# Plotar relação
plt.figure(figsize=(12, 6))
sns.scatterplot(data=price_by_year, x='year', y='mean_price', size='count', sizes=(20, 500))
plt.title('Preço Médio por Ano de Fabricação')
plt.xlabel('Ano')
plt.ylabel('Preço Médio ($)')
plt.show()

# Mostrar estatísticas
print("\nPreço médio por ano (últimos 10 anos):")
print(price_by_year.sort_values('year', ascending=False).head(10))"""),

        nbf.v4.new_markdown_cell("## 3. Quilometragem Média por Tipo de Combustível e Fabricante"),
        
        nbf.v4.new_code_cell("""# Por tipo de combustível
fuel_stats = df.groupby('fuel').agg({
    'odometer': ['mean', 'std', 'count']
}).round(2)
print("Quilometragem por tipo de combustível:")
print(fuel_stats)

# Por fabricante (top 10)
manufacturer_stats = df.groupby('manufacturer').agg({
    'odometer': ['mean', 'std', 'count']
}).round(2)
manufacturer_stats = manufacturer_stats.sort_values(('odometer', 'mean'), ascending=False)

plt.figure(figsize=(12, 6))
sns.barplot(data=manufacturer_stats.head(10).reset_index(), 
            x='manufacturer', 
            y=('odometer', 'mean'))
plt.xticks(rotation=45)
plt.title('Quilometragem Média por Fabricante (Top 10)')
plt.xlabel('Fabricante')
plt.ylabel('Quilometragem Média')
plt.show()"""),

        nbf.v4.new_markdown_cell("## 4. Correlação entre Quilometragem e Preço"),
        
        nbf.v4.new_code_cell("""# Calcular correlação
correlation = df['price'].corr(df['odometer'])
print(f"Coeficiente de correlação entre preço e quilometragem: {correlation:.4f}")

# Plotar relação
plt.figure(figsize=(12, 6))
sns.scatterplot(data=df, x='odometer', y='price', alpha=0.5)
plt.title(f'Relação entre Quilometragem e Preço (correlação = {correlation:.4f})')
plt.xlabel('Quilometragem')
plt.ylabel('Preço ($)')
plt.show()"""),

        nbf.v4.new_markdown_cell("## 5. Identificação de Outliers (IQR)"),
        
        nbf.v4.new_code_cell("""# Calcular IQR
Q1 = df['price'].quantile(0.25)
Q3 = df['price'].quantile(0.75)
IQR = Q3 - Q1

# Definir limites
lower_bound = Q1 - 1.5 * IQR
upper_bound = Q3 + 1.5 * IQR

# Identificar outliers
outliers = df[(df['price'] < lower_bound) | (df['price'] > upper_bound)]

print("Análise de Outliers:")
print(f"Q1: ${Q1:,.2f}")
print(f"Q3: ${Q3:,.2f}")
print(f"IQR: ${IQR:,.2f}")
print(f"Limite inferior: ${lower_bound:,.2f}")
print(f"Limite superior: ${upper_bound:,.2f}")
print(f"Número de outliers: {len(outliers)}")
print(f"Percentual de outliers: {(len(outliers)/len(df))*100:.2f}%")

# Plotar boxplot
plt.figure(figsize=(12, 6))
sns.boxplot(x=df['price'])
plt.title('Boxplot dos Preços')
plt.xlabel('Preço ($)')
plt.show()

# Mostrar alguns exemplos de outliers
print("\nExemplos de outliers (10 maiores preços):")
print(outliers.nlargest(10, 'price')[['manufacturer', 'model', 'year', 'price']])""")
    ]
    
    nb.cells = cells
    return nb

def create_sql_analysis_notebook():
    nb = nbf.v4.new_notebook()
    
    cells = [
        nbf.v4.new_markdown_cell("""# Análise SQL dos Dados de Veículos

Este notebook contém análises SQL dos dados de veículos usados, respondendo às seguintes questões:

1. Qual é o preço médio dos veículos por fabricante?
2. Quais são os 5 modelos mais anunciados e sua quilometragem média?
3. Quais são os 3 tipos de combustível mais comuns e sua quilometragem média?
4. Quais são as 5 regiões com maiores preços médios?
5. Qual a proporção de veículos manuais vs automáticos?"""),
        
        nbf.v4.new_code_cell("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

# Configurar visualização
plt.style.use('seaborn')
sns.set_palette('husl')

# Configurar conexão com o banco
load_dotenv()
engine = create_engine(
    f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
)"""),
        
        nbf.v4.new_markdown_cell("## 1. Preço Médio por Fabricante"),
        
        nbf.v4.new_code_cell("""query = '''
SELECT 
    manufacturer,
    COUNT(*) as total_vehicles,
    ROUND(AVG(price)::numeric, 2) as avg_price,
    ROUND(MIN(price)::numeric, 2) as min_price,
    ROUND(MAX(price)::numeric, 2) as max_price
FROM cars_cleaned
GROUP BY manufacturer
HAVING COUNT(*) > 10  -- Excluir fabricantes com poucos veículos
ORDER BY avg_price DESC;
'''

df_prices = pd.read_sql(query, engine)
print("Preço médio por fabricante:")
print(df_prices)

# Visualizar top 10
plt.figure(figsize=(12, 6))
sns.barplot(data=df_prices.head(10), x='manufacturer', y='avg_price')
plt.xticks(rotation=45)
plt.title('Top 10 Fabricantes por Preço Médio')
plt.xlabel('Fabricante')
plt.ylabel('Preço Médio ($)')
plt.show()"""),
        
        nbf.v4.new_markdown_cell("## 2. Top 5 Modelos Mais Anunciados"),
        
        nbf.v4.new_code_cell("""query = '''
WITH top_models AS (
    SELECT 
        manufacturer,
        model,
        COUNT(*) as total_ads,
        ROUND(AVG(odometer)::numeric, 2) as avg_odometer,
        ROUND(AVG(price)::numeric, 2) as avg_price
    FROM cars_cleaned
    GROUP BY manufacturer, model
    ORDER BY total_ads DESC
    LIMIT 5
)
SELECT * FROM top_models;
'''

df_models = pd.read_sql(query, engine)
print("Top 5 modelos mais anunciados:")
print(df_models)

# Visualizar
plt.figure(figsize=(12, 6))
sns.barplot(data=df_models, x='model', y='total_ads')
plt.xticks(rotation=45)
plt.title('Top 5 Modelos por Número de Anúncios')
plt.xlabel('Modelo')
plt.ylabel('Número de Anúncios')
plt.show()"""),
        
        nbf.v4.new_markdown_cell("## 3. Tipos de Combustível Mais Comuns"),
        
        nbf.v4.new_code_cell("""query = '''
SELECT 
    fuel,
    COUNT(*) as total_vehicles,
    ROUND(AVG(odometer)::numeric, 2) as avg_odometer,
    ROUND(AVG(price)::numeric, 2) as avg_price
FROM cars_cleaned
WHERE fuel IS NOT NULL AND fuel != 'unknown'
GROUP BY fuel
ORDER BY total_vehicles DESC
LIMIT 3;
'''

df_fuel = pd.read_sql(query, engine)
print("Top 3 tipos de combustível:")
print(df_fuel)

# Visualizar
plt.figure(figsize=(12, 6))
sns.barplot(data=df_fuel, x='fuel', y='avg_odometer')
plt.title('Quilometragem Média por Tipo de Combustível')
plt.xlabel('Tipo de Combustível')
plt.ylabel('Quilometragem Média')
plt.show()"""),
        
        nbf.v4.new_markdown_cell("## 4. Regiões com Maiores Preços Médios"),
        
        nbf.v4.new_code_cell("""query = '''
SELECT 
    state,
    COUNT(*) as total_vehicles,
    ROUND(AVG(price)::numeric, 2) as avg_price,
    ROUND(MIN(price)::numeric, 2) as min_price,
    ROUND(MAX(price)::numeric, 2) as max_price
FROM cars_cleaned
WHERE state IS NOT NULL
GROUP BY state
HAVING COUNT(*) > 50  -- Excluir estados com poucos veículos
ORDER BY avg_price DESC
LIMIT 5;
'''

df_states = pd.read_sql(query, engine)
print("Top 5 estados por preço médio:")
print(df_states)

# Visualizar
plt.figure(figsize=(12, 6))
sns.barplot(data=df_states, x='state', y='avg_price')
plt.title('Preço Médio por Estado (Top 5)')
plt.xlabel('Estado')
plt.ylabel('Preço Médio ($)')
plt.show()"""),
        
        nbf.v4.new_markdown_cell("## 5. Proporção de Transmissão Manual vs Automática"),
        
        nbf.v4.new_code_cell("""query = '''
WITH transmission_counts AS (
    SELECT 
        CASE 
            WHEN LOWER(transmission) LIKE '%manual%' THEN 'Manual'
            WHEN LOWER(transmission) LIKE '%auto%' THEN 'Automático'
            ELSE 'Outros'
        END as transmission_type,
        COUNT(*) as total
    FROM cars_cleaned
    WHERE transmission IS NOT NULL
    GROUP BY 1
)
SELECT 
    transmission_type,
    total,
    ROUND((total::float / SUM(total) OVER()) * 100, 2) as percentage
FROM transmission_counts
ORDER BY total DESC;
'''

df_transmission = pd.read_sql(query, engine)
print("Distribuição por tipo de transmissão:")
print(df_transmission)

# Visualizar
plt.figure(figsize=(10, 10))
plt.pie(df_transmission['total'], labels=df_transmission['transmission_type'], 
        autopct='%1.1f%%', startangle=90)
plt.title('Proporção de Tipos de Transmissão')
plt.axis('equal')
plt.show()""")
    ]
    
    nb.cells = cells
    return nb

def create_advanced_sql_notebook():
    """Creates a notebook with advanced SQL analyses."""
    nb = nbf.v4.new_notebook()
    
    # Title and Introduction
    nb['cells'].append(nbf.v4.new_markdown_cell('''# Análises SQL Avançadas - Carros Usados

Este notebook contém análises SQL avançadas do dataset de carros usados, explorando diferentes aspectos dos dados como:
1. Valor por idade e quilometragem
2. Sazonalidade de vendas
3. Relação entre cores e preços
4. Análise geográfica
5. Condição vs preço por fabricante
6. Eficiência de combustível por tipo
'''))

    # Setup cell
    nb['cells'].append(nbf.v4.new_code_cell('''import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

# Configurar visualização
plt.style.use('seaborn')
sns.set_palette('husl')
plt.rcParams['figure.figsize'] = [12, 6]

# Configurar conexão com o banco
load_dotenv()
engine = create_engine(
    f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
)'''))

    # 1. Análise de Valor por Idade e Quilometragem
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 1. Análise de Valor por Idade e Quilometragem

Esta análise nos mostra quais modelos mantêm melhor seu valor ao longo do tempo e quilometragem.'''))

    nb['cells'].append(nbf.v4.new_code_cell('''query = """
WITH vehicle_metrics AS (
    SELECT 
        manufacturer,
        model,
        year,
        price,
        odometer,
        (2024 - year) as age,
        price / NULLIF(odometer, 0) * 1000 as price_per_1000_miles
    FROM cars_cleaned
    WHERE odometer > 0
)
SELECT 
    manufacturer,
    model,
    ROUND(AVG(price)::numeric, 2) as avg_price,
    ROUND(AVG(age)::numeric, 1) as avg_age,
    ROUND(AVG(price_per_1000_miles)::numeric, 2) as avg_price_per_1000_miles,
    COUNT(*) as total_vehicles
FROM vehicle_metrics
GROUP BY manufacturer, model
HAVING COUNT(*) >= 10
ORDER BY avg_price_per_1000_miles DESC
LIMIT 15;
"""

df_value = pd.read_sql(query, engine)
print("Top 15 modelos que melhor mantêm seu valor:")
print(df_value.to_string(index=False))

# Visualização
plt.figure(figsize=(12, 6))
sns.barplot(data=df_value.head(10), 
            x='model', 
            y='price_per_1000_miles', 
            hue='manufacturer')
plt.xticks(rotation=45)
plt.title('Top 10 Modelos - Preço por 1000 Milhas')
plt.tight_layout()
plt.show()'''))

    # 2. Análise de Sazonalidade
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 2. Análise de Sazonalidade

Vamos analisar padrões sazonais nas vendas e preços dos veículos.'''))

    nb['cells'].append(nbf.v4.new_code_cell('''query = """
SELECT 
    EXTRACT(MONTH FROM posting_date) as month,
    COUNT(*) as total_listings,
    ROUND(AVG(price)::numeric, 2) as avg_price,
    ROUND(MIN(price)::numeric, 2) as min_price,
    ROUND(MAX(price)::numeric, 2) as max_price
FROM cars_cleaned
WHERE posting_date IS NOT NULL
GROUP BY EXTRACT(MONTH FROM posting_date)
ORDER BY month;
"""

df_seasonal = pd.read_sql(query, engine)
print("Estatísticas mensais:")
print(df_seasonal.to_string(index=False))

# Visualizações
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

# Gráfico de total de anúncios
sns.barplot(data=df_seasonal, x='month', y='total_listings', ax=ax1)
ax1.set_title('Total de Anúncios por Mês')
ax1.set_xlabel('Mês')
ax1.set_ylabel('Total de Anúncios')

# Gráfico de preço médio
sns.lineplot(data=df_seasonal, x='month', y='avg_price', ax=ax2)
ax2.set_title('Preço Médio por Mês')
ax2.set_xlabel('Mês')
ax2.set_ylabel('Preço Médio ($)')

plt.tight_layout()
plt.show()'''))

    # 3. Análise de Cores e Preços
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 3. Análise de Cores e Preços por Tipo de Veículo

Esta análise revela preferências de cor por tipo de veículo e seu impacto nos preços.'''))

    nb['cells'].append(nbf.v4.new_code_cell('''query = """
SELECT 
    type,
    paint_color,
    COUNT(*) as total_vehicles,
    ROUND(AVG(price)::numeric, 2) as avg_price,
    ROUND(AVG(odometer)::numeric, 2) as avg_mileage
FROM cars_cleaned
WHERE type != 'unknown' 
AND paint_color != 'unknown'
GROUP BY type, paint_color
HAVING COUNT(*) > 10
ORDER BY type, avg_price DESC;
"""

df_colors = pd.read_sql(query, engine)
print("Análise de cores por tipo de veículo:")
print(df_colors.to_string(index=False))

# Criar um heatmap de preços médios
pivot_table = df_colors.pivot(index='type', columns='paint_color', values='avg_price')
plt.figure(figsize=(12, 8))
sns.heatmap(pivot_table, annot=True, fmt='.0f', cmap='YlOrRd')
plt.title('Preço Médio por Tipo de Veículo e Cor')
plt.tight_layout()
plt.show()'''))

    # 4. Análise Geográfica
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 4. Análise Geográfica de Preços

Vamos explorar como os preços variam por estado e região.'''))

    nb['cells'].append(nbf.v4.new_code_cell('''query = """
WITH state_metrics AS (
    SELECT 
        state,
        COUNT(*) as total_listings,
        ROUND(AVG(price)::numeric, 2) as avg_price,
        ROUND(STDDEV(price)::numeric, 2) as price_stddev,
        ROUND(AVG(odometer)::numeric, 2) as avg_mileage
    FROM cars_cleaned
    WHERE state IS NOT NULL
    GROUP BY state
    HAVING COUNT(*) >= 50
)
SELECT 
    state,
    total_listings,
    avg_price,
    price_stddev,
    avg_mileage,
    ROUND((price_stddev / avg_price * 100)::numeric, 2) as price_variation_pct
FROM state_metrics
ORDER BY price_variation_pct DESC;
"""

df_geo = pd.read_sql(query, engine)
print("Análise geográfica de preços:")
print(df_geo.to_string(index=False))

# Visualizações
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

# Preço médio por estado
sns.barplot(data=df_geo.sort_values('avg_price', ascending=False).head(10), 
            x='state', y='avg_price', ax=ax1)
ax1.set_title('Top 10 Estados - Preço Médio')
ax1.set_xlabel('Estado')
ax1.set_ylabel('Preço Médio ($)')

# Variação de preço por estado
sns.barplot(data=df_geo.sort_values('price_variation_pct', ascending=False).head(10), 
            x='state', y='price_variation_pct', ax=ax2)
ax2.set_title('Top 10 Estados - Variação de Preço (%)')
ax2.set_xlabel('Estado')
ax2.set_ylabel('Variação de Preço (%)')

plt.tight_layout()
plt.show()'''))

    # 5. Análise de Condição vs Preço
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 5. Análise de Condição vs Preço por Fabricante

Esta análise mostra como a condição do veículo afeta seu preço para diferentes fabricantes.'''))

    nb['cells'].append(nbf.v4.new_code_cell('''query = """
SELECT 
    manufacturer,
    condition,
    COUNT(*) as total_vehicles,
    ROUND(AVG(price)::numeric, 2) as avg_price,
    ROUND(AVG(odometer)::numeric, 2) as avg_mileage,
    ROUND(AVG(2024 - year)::numeric, 1) as avg_age
FROM cars_cleaned
WHERE condition != 'unknown'
GROUP BY manufacturer, condition
HAVING COUNT(*) >= 5
ORDER BY manufacturer, avg_price DESC;
"""

df_condition = pd.read_sql(query, engine)
print("Análise de condição por fabricante:")
print(df_condition.to_string(index=False))

# Criar um gráfico para os top 10 fabricantes
top_manufacturers = df_condition.groupby('manufacturer')['total_vehicles'].sum().nlargest(10).index

plt.figure(figsize=(12, 6))
sns.barplot(data=df_condition[df_condition['manufacturer'].isin(top_manufacturers)], 
            x='manufacturer', y='avg_price', hue='condition')
plt.xticks(rotation=45)
plt.title('Preço Médio por Fabricante e Condição')
plt.tight_layout()
plt.show()'''))

    # 6. Análise de Eficiência de Combustível
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 6. Análise de Eficiência de Combustível por Tipo

Vamos analisar a distribuição de tipos de combustível por categoria de veículo.'''))

    nb['cells'].append(nbf.v4.new_code_cell('''query = """
SELECT 
    fuel,
    type,
    COUNT(*) as total_vehicles,
    ROUND(AVG(price)::numeric, 2) as avg_price,
    ROUND(AVG(odometer)::numeric, 2) as avg_mileage,
    ROUND(AVG(2024 - year)::numeric, 1) as avg_age,
    COUNT(DISTINCT manufacturer) as unique_manufacturers
FROM cars_cleaned
WHERE fuel != 'unknown' 
AND type != 'unknown'
GROUP BY fuel, type
HAVING COUNT(*) >= 10
ORDER BY fuel, avg_price DESC;
"""

df_fuel = pd.read_sql(query, engine)
print("Análise de combustível por tipo de veículo:")
print(df_fuel.to_string(index=False))

# Criar um gráfico de barras empilhadas
pivot_table = df_fuel.pivot_table(index='type', columns='fuel', values='total_vehicles', fill_value=0)
pivot_table_pct = pivot_table.div(pivot_table.sum(axis=1), axis=0) * 100

plt.figure(figsize=(12, 6))
pivot_table_pct.plot(kind='bar', stacked=True)
plt.title('Distribuição de Tipos de Combustível por Categoria de Veículo')
plt.xlabel('Tipo de Veículo')
plt.ylabel('Porcentagem')
plt.legend(title='Tipo de Combustível', bbox_to_anchor=(1.05, 1))
plt.tight_layout()
plt.show()'''))

    # Save the notebook
    os.makedirs('notebooks', exist_ok=True)
    with open('notebooks/advanced_sql_analysis.ipynb', 'w', encoding='utf-8') as f:
        nbf.write(nb, f)

def create_ml_analysis_notebook():
    """Creates a notebook for machine learning and time series analysis."""
    nb = nbf.v4.new_notebook()
    
    # Title and Introduction
    nb['cells'].append(nbf.v4.new_markdown_cell('''# Análise de Machine Learning e Séries Temporais

Este notebook explora aplicações de machine learning e análise de séries temporais nos dados de carros usados:

1. Previsão de Preços (Regressão)
2. Análise de Tendências Temporais
3. Segmentação de Veículos (Clustering)
4. Análise de Sazonalidade e Decomposição
5. Previsão de Volume de Vendas
'''))

    # Setup e imports
    nb['cells'].append(nbf.v4.new_code_cell('''import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

# Bibliotecas de ML
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score

# Bibliotecas de Séries Temporais
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import adfuller
from prophet import Prophet

# Bibliotecas de Clustering
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

# Configurações de visualização
plt.style.use('seaborn')
sns.set_palette('husl')
plt.rcParams['figure.figsize'] = [12, 6]

# Conexão com o banco
load_dotenv()
engine = create_engine(
    f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
)

# Carregar dados
df = pd.read_sql("""
    SELECT *
    FROM cars_cleaned
    WHERE price > 0 
    AND year >= 1990
    AND posting_date IS NOT NULL
""", engine)'''))

    # 1. Previsão de Preços
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 1. Previsão de Preços

Vamos criar um modelo de machine learning para prever preços de veículos baseado em suas características.'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Preparar features
features = ['year', 'manufacturer', 'model', 'condition', 'odometer', 
            'fuel', 'transmission', 'drive', 'type', 'paint_color']
target = 'price'

# Separar features numéricas e categóricas
numeric_features = ['year', 'odometer']
categorical_features = ['manufacturer', 'model', 'condition', 'fuel', 
                       'transmission', 'drive', 'type', 'paint_color']

# Criar preprocessador
preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), numeric_features),
        ('cat', OneHotEncoder(drop='first', sparse=False), categorical_features)
    ])

# Criar pipeline
model = Pipeline([
    ('preprocessor', preprocessor),
    ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))
])

# Separar dados
X = df[features]
y = df[target]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Treinar modelo
print("Treinando modelo de previsão de preços...")
model.fit(X_train, y_train)

# Avaliar modelo
y_pred = model.predict(X_test)
mse = mean_squared_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"Erro Quadrático Médio: ${np.sqrt(mse):,.2f}")
print(f"R² Score: {r2:.4f}")

# Visualizar previsões vs valores reais
plt.figure(figsize=(10, 6))
plt.scatter(y_test, y_pred, alpha=0.5)
plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
plt.xlabel('Preço Real')
plt.ylabel('Preço Previsto')
plt.title('Previsão de Preços: Valores Reais vs Previstos')
plt.tight_layout()
plt.show()

# Importância das features
feature_importance = pd.DataFrame({
    'feature': numeric_features + categorical_features,
    'importance': model.named_steps['regressor'].feature_importances_[:len(numeric_features) + len(categorical_features)]
})
feature_importance = feature_importance.sort_values('importance', ascending=False)

plt.figure(figsize=(10, 6))
sns.barplot(data=feature_importance.head(10), x='importance', y='feature')
plt.title('Top 10 Features Mais Importantes')
plt.tight_layout()
plt.show()'''))

    # 2. Análise de Tendências Temporais
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 2. Análise de Tendências Temporais

Vamos analisar tendências temporais nos preços e volume de vendas.'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Preparar dados temporais
df['posting_date'] = pd.to_datetime(df['posting_date'])
df_temporal = df.set_index('posting_date')

# Análise diária
daily_stats = df_temporal.resample('D').agg({
    'price': ['mean', 'count'],
    'odometer': 'mean'
}).dropna()

daily_stats.columns = ['price_mean', 'listings_count', 'odometer_mean']

# Plotar tendências
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

# Preço médio ao longo do tempo
daily_stats['price_mean'].plot(ax=ax1)
ax1.set_title('Evolução do Preço Médio')
ax1.set_xlabel('Data')
ax1.set_ylabel('Preço Médio ($)')

# Volume de listagens
daily_stats['listings_count'].plot(ax=ax2)
ax2.set_title('Volume de Listagens Diárias')
ax2.set_xlabel('Data')
ax2.set_ylabel('Número de Listagens')

plt.tight_layout()
plt.show()

# Teste de estacionariedade
def test_stationarity(timeseries):
    result = adfuller(timeseries.dropna())
    print('Teste de Dickey-Fuller Aumentado:')
    print(f'Estatística de teste: {result[0]:.4f}')
    print(f'p-value: {result[1]:.4f}')
    print('Valores Críticos:')
    for key, value in result[4].items():
        print(f'\\t{key}: {value:.4f}')

print("\\nTestando estacionariedade do preço médio:")
test_stationarity(daily_stats['price_mean'])'''))

    # 3. Segmentação de Veículos
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 3. Segmentação de Veículos

Vamos usar clustering para identificar segmentos naturais no mercado de veículos.'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Preparar dados para clustering
cluster_features = ['price', 'year', 'odometer']
X_cluster = df[cluster_features].copy()

# Normalizar dados
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X_cluster)

# Encontrar número ótimo de clusters
inertias = []
K = range(1, 11)
for k in K:
    kmeans = KMeans(n_clusters=k, random_state=42)
    kmeans.fit(X_scaled)
    inertias.append(kmeans.inertia_)

# Plotar elbow curve
plt.figure(figsize=(10, 6))
plt.plot(K, inertias, 'bx-')
plt.xlabel('k')
plt.ylabel('Inertia')
plt.title('Elbow Method para Número Ótimo de Clusters')
plt.show()

# Aplicar K-means com número ótimo de clusters
n_clusters = 4  # Baseado no elbow plot
kmeans = KMeans(n_clusters=n_clusters, random_state=42)
df['cluster'] = kmeans.fit_predict(X_scaled)

# Analisar clusters
cluster_stats = df.groupby('cluster').agg({
    'price': ['mean', 'count'],
    'year': 'mean',
    'odometer': 'mean'
}).round(2)

print("\\nEstatísticas dos clusters:")
print(cluster_stats)

# Visualizar clusters
plt.figure(figsize=(12, 8))
scatter = plt.scatter(df['year'], df['price'], 
                     c=df['cluster'], cmap='viridis',
                     alpha=0.6)
plt.colorbar(scatter)
plt.xlabel('Ano')
plt.ylabel('Preço')
plt.title('Segmentação de Veículos')
plt.show()'''))

    # 4. Análise de Sazonalidade
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 4. Análise de Sazonalidade e Decomposição

Vamos decompor as séries temporais para identificar padrões sazonais.'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Preparar série temporal mensal
monthly_stats = df_temporal.resample('M').agg({
    'price': ['mean', 'count'],
    'odometer': 'mean'
}).dropna()

# Decomposição da série de preços
decomposition = seasonal_decompose(monthly_stats[('price', 'mean')], 
                                 period=12,
                                 extrapolate_trend='freq')

# Plotar decomposição
fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(12, 12))

decomposition.observed.plot(ax=ax1)
ax1.set_title('Série Original')

decomposition.trend.plot(ax=ax2)
ax2.set_title('Tendência')

decomposition.seasonal.plot(ax=ax3)
ax3.set_title('Sazonalidade')

decomposition.resid.plot(ax=ax4)
ax4.set_title('Resíduos')

plt.tight_layout()
plt.show()

# Análise mensal
monthly_pattern = df.groupby(df['posting_date'].dt.month).agg({
    'price': ['mean', 'count'],
    'odometer': 'mean'
}).round(2)

print("\\nPadrão mensal:")
print(monthly_pattern)

# Visualizar padrão mensal
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

monthly_pattern[('price', 'mean')].plot(kind='bar', ax=ax1)
ax1.set_title('Preço Médio por Mês')
ax1.set_xlabel('Mês')
ax1.set_ylabel('Preço Médio ($)')

monthly_pattern[('price', 'count')].plot(kind='bar', ax=ax2)
ax2.set_title('Volume de Vendas por Mês')
ax2.set_xlabel('Mês')
ax2.set_ylabel('Número de Listagens')

plt.tight_layout()
plt.show()'''))

    # 5. Previsão de Volume de Vendas
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 5. Previsão de Volume de Vendas

Vamos usar o Facebook Prophet para prever o volume futuro de vendas.'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Preparar dados para Prophet
prophet_df = daily_stats.reset_index()[['posting_date', 'listings_count']]
prophet_df.columns = ['ds', 'y']

# Criar e treinar modelo
model = Prophet(yearly_seasonality=True, 
               weekly_seasonality=True,
               daily_seasonality=False)
model.fit(prophet_df)

# Fazer previsões
future = model.make_future_dataframe(periods=90)  # Próximos 90 dias
forecast = model.predict(future)

# Plotar previsões
fig = model.plot(forecast)
plt.title('Previsão de Volume de Vendas')
plt.show()

# Plotar componentes
fig = model.plot_components(forecast)
plt.show()

# Métricas de previsão
metrics = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(90)
print("\\nPrevisões para os próximos 90 dias:")
print(metrics.head())'''))

    # Save the notebook
    os.makedirs('notebooks', exist_ok=True)
    with open('notebooks/ml_analysis.ipynb', 'w', encoding='utf-8') as f:
        nbf.write(nb, f)

def create_advanced_ml_notebook():
    """Creates a notebook with advanced machine learning analyses."""
    nb = nbf.v4.new_notebook()
    
    # Title and Introduction
    nb['cells'].append(nbf.v4.new_markdown_cell('''# Análises Avançadas de Machine Learning

Este notebook implementa análises avançadas de machine learning no dataset de carros usados:

1. Previsão de Preços Avançada
   - Comparação de múltiplos modelos
   - Otimização de hiperparâmetros
   - Cross-validation
   - Feature engineering avançado

2. Análise de Séries Temporais
   - Modelos ARIMA/SARIMA
   - Análise de eventos especiais
   - Correlação com variáveis econômicas
   - Previsão multivariada

3. Clustering Avançado
   - Múltiplos algoritmos
   - Análise detalhada de clusters
   - Segmentação geográfica
   - Análise de mercado-alvo

4. Análises Complementares
   - Detecção de anomalias
   - Análise de sentimento
   - Sistema de recomendação
   - Análise de competitividade
'''))

    # Setup e imports
    nb['cells'].append(nbf.v4.new_code_cell('''import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

# Bibliotecas de ML
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, OneHotEncoder, RobustScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LassoCV, RidgeCV
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

# Bibliotecas de Séries Temporais
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.statespace.sarimax import SARIMAX
from prophet import Prophet

# Bibliotecas de Clustering
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import silhouette_score

# Bibliotecas de NLP
from textblob import TextBlob
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')

# Bibliotecas de Detecção de Anomalias
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor

# Configurações de visualização
plt.style.use('seaborn')
sns.set_palette('husl')
plt.rcParams['figure.figsize'] = [12, 6]

# Conexão com o banco
load_dotenv()
engine = create_engine(
    f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
)

# Carregar dados
df = pd.read_sql("""
    SELECT *
    FROM cars_cleaned
    WHERE price > 0 
    AND year >= 1990
    AND posting_date IS NOT NULL
""", engine)'''))

    # 1. Previsão de Preços Avançada
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 1. Previsão de Preços Avançada

### 1.1 Feature Engineering Avançado'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Feature Engineering
def create_features(df):
    # Criar cópia para não modificar o original
    df_feat = df.copy()
    
    # Features temporais
    df_feat['vehicle_age'] = 2024 - df_feat['year']
    df_feat['price_per_year'] = df_feat['price'] / df_feat['vehicle_age']
    df_feat['price_per_mile'] = df_feat['price'] / df_feat['odometer']
    
    # Features categóricas agregadas
    price_by_manufacturer = df_feat.groupby('manufacturer')['price'].mean()
    df_feat['manufacturer_avg_price'] = df_feat['manufacturer'].map(price_by_manufacturer)
    
    # Interações
    df_feat['age_mileage_ratio'] = df_feat['vehicle_age'] / df_feat['odometer']
    
    # Features de texto
    df_feat['description_length'] = df_feat['description'].str.len()
    df_feat['title_status_encoded'] = pd.get_dummies(df_feat['title_status'], drop_first=True)
    
    return df_feat

# Aplicar feature engineering
df_featured = create_features(df)

# Selecionar features
features = ['year', 'manufacturer', 'model', 'condition', 'odometer',
           'fuel', 'transmission', 'drive', 'type', 'paint_color',
           'vehicle_age', 'price_per_year', 'price_per_mile',
           'manufacturer_avg_price', 'age_mileage_ratio',
           'description_length']
target = 'price'

# Separar features numéricas e categóricas
numeric_features = ['year', 'odometer', 'vehicle_age', 'price_per_year',
                   'price_per_mile', 'manufacturer_avg_price',
                   'age_mileage_ratio', 'description_length']
categorical_features = ['manufacturer', 'model', 'condition', 'fuel',
                       'transmission', 'drive', 'type', 'paint_color']'''))

    nb['cells'].append(nbf.v4.new_markdown_cell('''### 1.2 Comparação de Múltiplos Modelos'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Preparar preprocessador
preprocessor = ColumnTransformer(
    transformers=[
        ('num', RobustScaler(), numeric_features),
        ('cat', OneHotEncoder(drop='first', sparse=False), categorical_features)
    ])

# Definir modelos para comparação
models = {
    'RandomForest': RandomForestRegressor(random_state=42),
    'XGBoost': XGBRegressor(random_state=42),
    'LightGBM': LGBMRegressor(random_state=42),
    'GradientBoosting': GradientBoostingRegressor(random_state=42),
    'Lasso': LassoCV(random_state=42),
    'Ridge': RidgeCV()
}

# Separar dados
X = df_featured[features]
y = df_featured[target]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Avaliar cada modelo
results = []
for name, model in models.items():
    # Criar pipeline
    pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('regressor', model)
    ])
    
    # Treinar e avaliar
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    
    # Calcular métricas
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    results.append({
        'Model': name,
        'RMSE': rmse,
        'MAE': mae,
        'R2': r2
    })

# Mostrar resultados
results_df = pd.DataFrame(results)
print("Comparação de Modelos:")
print(results_df)

# Visualizar comparação
plt.figure(figsize=(12, 6))
sns.barplot(data=results_df, x='Model', y='R2')
plt.title('Comparação de R² entre Modelos')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()'''))

    nb['cells'].append(nbf.v4.new_markdown_cell('''### 1.3 Otimização de Hiperparâmetros'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Selecionar melhor modelo (XGBoost como exemplo)
best_model = XGBRegressor(random_state=42)

# Definir grid de hiperparâmetros
param_grid = {
    'regressor__n_estimators': [100, 200, 300],
    'regressor__max_depth': [3, 4, 5],
    'regressor__learning_rate': [0.01, 0.1, 0.3],
    'regressor__subsample': [0.8, 0.9, 1.0]
}

# Criar pipeline
pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('regressor', best_model)
])

# Realizar Grid Search com Cross-validation
grid_search = GridSearchCV(
    pipeline,
    param_grid,
    cv=5,
    scoring='r2',
    n_jobs=-1
)

# Treinar modelo
print("Otimizando hiperparâmetros...")
grid_search.fit(X_train, y_train)

# Mostrar melhores parâmetros
print("\nMelhores parâmetros:")
print(grid_search.best_params_)

# Avaliar modelo otimizado
y_pred = grid_search.predict(X_test)
print("\nMétricas do modelo otimizado:")
print(f"R² Score: {r2_score(y_test, y_pred):.4f}")
print(f"RMSE: ${np.sqrt(mean_squared_error(y_test, y_pred)):,.2f}")

# Visualizar previsões
plt.figure(figsize=(10, 6))
plt.scatter(y_test, y_pred, alpha=0.5)
plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
plt.xlabel('Preço Real')
plt.ylabel('Preço Previsto')
plt.title('Previsões do Modelo Otimizado')
plt.tight_layout()
plt.show()'''))

    # 2. Análise de Séries Temporais Avançada
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 2. Análise de Séries Temporais Avançada

### 2.1 Análise SARIMA'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Preparar dados temporais
df['posting_date'] = pd.to_datetime(df['posting_date'])
df_temporal = df.set_index('posting_date')

# Análise diária
daily_stats = df_temporal.resample('D').agg({
    'price': ['mean', 'count'],
    'odometer': 'mean'
}).dropna()

daily_stats.columns = ['price_mean', 'listings_count', 'odometer_mean']

# Ajustar modelo SARIMA
model = SARIMAX(daily_stats['price_mean'],
                order=(1, 1, 1),
                seasonal_order=(1, 1, 1, 12))
results = model.fit()

# Fazer previsões
forecast = results.get_forecast(steps=30)
forecast_mean = forecast.predicted_mean
forecast_ci = forecast.conf_int()

# Plotar resultados
plt.figure(figsize=(12, 6))
plt.plot(daily_stats.index, daily_stats['price_mean'], label='Observado')
plt.plot(forecast_mean.index, forecast_mean, color='r', label='Previsão')
plt.fill_between(forecast_ci.index,
                 forecast_ci.iloc[:, 0],
                 forecast_ci.iloc[:, 1], color='r', alpha=.1)
plt.title('Previsão SARIMA - Preço Médio')
plt.legend()
plt.show()

# Mostrar métricas do modelo
print("\nResumo do modelo SARIMA:")
print(results.summary())'''))

    nb['cells'].append(nbf.v4.new_markdown_cell('''### 2.2 Análise de Eventos Especiais'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Identificar eventos especiais (picos e vales)
def detect_events(series, window=30, threshold=2):
    rolling_mean = series.rolling(window=window).mean()
    rolling_std = series.rolling(window=window).std()
    
    z_scores = (series - rolling_mean) / rolling_std
    events = z_scores[abs(z_scores) > threshold]
    
    return events

# Detectar eventos nos preços
price_events = detect_events(daily_stats['price_mean'])
volume_events = detect_events(daily_stats['listings_count'])

# Visualizar eventos
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

# Preços
daily_stats['price_mean'].plot(ax=ax1, alpha=0.5)
ax1.scatter(price_events.index, price_events.index.map(daily_stats['price_mean']),
            color='red', label='Eventos')
ax1.set_title('Eventos Especiais - Preços')
ax1.legend()

# Volume
daily_stats['listings_count'].plot(ax=ax2, alpha=0.5)
ax2.scatter(volume_events.index, volume_events.index.map(daily_stats['listings_count']),
            color='red', label='Eventos')
ax2.set_title('Eventos Especiais - Volume')
ax2.legend()

plt.tight_layout()
plt.show()

# Analisar eventos
print("\nEventos de Preço:")
print(price_events.head())
print("\nEventos de Volume:")
print(volume_events.head())'''))

    # 3. Clustering Avançado
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 3. Clustering Avançado

### 3.1 Comparação de Algoritmos de Clustering'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Preparar dados para clustering
cluster_features = ['price', 'year', 'odometer', 'vehicle_age', 
                   'price_per_year', 'price_per_mile']
X_cluster = df_featured[cluster_features].copy()

# Normalizar dados
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X_cluster)

# Definir algoritmos
clustering_algorithms = {
    'K-means': KMeans(n_clusters=4, random_state=42),
    'DBSCAN': DBSCAN(eps=0.3, min_samples=10),
    'Agglomerative': AgglomerativeClustering(n_clusters=4)
}

# Aplicar e avaliar cada algoritmo
results = {}
for name, algorithm in clustering_algorithms.items():
    # Aplicar clustering
    labels = algorithm.fit_predict(X_scaled)
    
    # Calcular métricas (quando possível)
    if name != 'DBSCAN':
        silhouette = silhouette_score(X_scaled, labels)
    else:
        silhouette = silhouette_score(X_scaled, labels[labels != -1])
    
    # Guardar resultados
    results[name] = {
        'labels': labels,
        'silhouette': silhouette
    }
    
    # Visualizar clusters
    plt.figure(figsize=(10, 6))
    scatter = plt.scatter(df_featured['year'], df_featured['price'],
                         c=labels, cmap='viridis', alpha=0.6)
    plt.colorbar(scatter)
    plt.xlabel('Ano')
    plt.ylabel('Preço')
    plt.title(f'Clusters usando {name}')
    plt.show()
    
    # Mostrar estatísticas dos clusters
    cluster_stats = pd.DataFrame({
        'cluster': labels,
        'price': df_featured['price'],
        'year': df_featured['year'],
        'odometer': df_featured['odometer']
    }).groupby('cluster').agg({
        'price': ['mean', 'count'],
        'year': 'mean',
        'odometer': 'mean'
    }).round(2)
    
    print(f"\nEstatísticas dos clusters ({name}):")
    print(cluster_stats)
    print(f"Silhouette Score: {silhouette:.4f}")'''))

    nb['cells'].append(nbf.v4.new_markdown_cell('''### 3.2 Análise de Mercado-Alvo'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Usar o melhor modelo de clustering (K-means como exemplo)
best_clustering = KMeans(n_clusters=4, random_state=42)
df_featured['cluster'] = best_clustering.fit_predict(X_scaled)

# Análise por cluster
cluster_analysis = df_featured.groupby('cluster').agg({
    'price': ['mean', 'std', 'count'],
    'year': ['mean', 'min', 'max'],
    'odometer': 'mean',
    'manufacturer': lambda x: x.value_counts().index[0],
    'model': lambda x: x.value_counts().index[0],
    'fuel': lambda x: x.value_counts().index[0],
    'transmission': lambda x: x.value_counts().index[0]
}).round(2)

print("Análise detalhada dos segmentos de mercado:")
print(cluster_analysis)

# Visualizar características dos clusters
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

# Preço médio por cluster
sns.boxplot(data=df_featured, x='cluster', y='price', ax=ax1)
ax1.set_title('Distribuição de Preços por Cluster')

# Ano médio por cluster
sns.boxplot(data=df_featured, x='cluster', y='year', ax=ax2)
ax2.set_title('Distribuição de Anos por Cluster')

# Quilometragem média por cluster
sns.boxplot(data=df_featured, x='cluster', y='odometer', ax=ax3)
ax3.set_title('Distribuição de Quilometragem por Cluster')

# Distribuição de fabricantes por cluster
manufacturer_cluster = pd.crosstab(df_featured['cluster'], 
                                 df_featured['manufacturer'])
manufacturer_cluster_pct = manufacturer_cluster.div(
    manufacturer_cluster.sum(axis=1), axis=0)
sns.heatmap(manufacturer_cluster_pct, ax=ax4, cmap='YlOrRd')
ax4.set_title('Distribuição de Fabricantes por Cluster')

plt.tight_layout()
plt.show()'''))

    # 4. Análises Complementares
    nb['cells'].append(nbf.v4.new_markdown_cell('''## 4. Análises Complementares

### 4.1 Detecção de Anomalias'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Preparar dados para detecção de anomalias
anomaly_features = ['price', 'year', 'odometer', 'price_per_mile']
X_anomaly = df_featured[anomaly_features].copy()
X_anomaly_scaled = scaler.fit_transform(X_anomaly)

# Aplicar diferentes métodos de detecção
# Isolation Forest
iso_forest = IsolationForest(contamination=0.1, random_state=42)
iso_forest_labels = iso_forest.fit_predict(X_anomaly_scaled)

# Local Outlier Factor
lof = LocalOutlierFactor(contamination=0.1)
lof_labels = lof.fit_predict(X_anomaly_scaled)

# Visualizar resultados
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

# Isolation Forest
scatter1 = ax1.scatter(df_featured['year'], df_featured['price'],
                      c=iso_forest_labels, cmap='RdYlBu')
ax1.set_title('Anomalias (Isolation Forest)')
ax1.set_xlabel('Ano')
ax1.set_ylabel('Preço')
plt.colorbar(scatter1, ax=ax1)

# Local Outlier Factor
scatter2 = ax2.scatter(df_featured['year'], df_featured['price'],
                      c=lof_labels, cmap='RdYlBu')
ax2.set_title('Anomalias (Local Outlier Factor)')
ax2.set_xlabel('Ano')
ax2.set_ylabel('Preço')
plt.colorbar(scatter2, ax=ax2)

plt.tight_layout()
plt.show()

# Analisar anomalias detectadas
print("\nEstatísticas das anomalias detectadas:")
for method, labels in [('Isolation Forest', iso_forest_labels),
                      ('LOF', lof_labels)]:
    anomalies = df_featured[labels == -1]
    print(f"\n{method}:")
    print(f"Número de anomalias: {len(anomalies)}")
    print("\nExemplos de anomalias:")
    print(anomalies[['manufacturer', 'model', 'year', 'price',
                     'odometer']].head())'''))

    nb['cells'].append(nbf.v4.new_markdown_cell('''### 4.2 Análise de Sentimento das Descrições'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Função para análise de sentimento
def analyze_sentiment(text):
    try:
        return TextBlob(str(text)).sentiment.polarity
    except:
        return 0

# Aplicar análise de sentimento
df_featured['sentiment'] = df_featured['description'].apply(analyze_sentiment)

# Análise básica de sentimento
print("Estatísticas de sentimento:")
print(df_featured['sentiment'].describe())

# Relação entre sentimento e preço
plt.figure(figsize=(10, 6))
plt.scatter(df_featured['sentiment'], df_featured['price'], alpha=0.5)
plt.xlabel('Sentimento')
plt.ylabel('Preço')
plt.title('Relação entre Sentimento da Descrição e Preço')
plt.show()

# Palavras mais comuns por faixa de preço
def get_top_words(texts, n=10):
    words = ' '.join(texts).lower()
    tokens = word_tokenize(words)
    stop_words = set(stopwords.words('english'))
    words_filtered = [word for word in tokens if word.isalnum() and
                     word not in stop_words]
    return pd.Series(words_filtered).value_counts().head(n)

# Dividir em faixas de preço
df_featured['price_category'] = pd.qcut(df_featured['price'], q=3,
                                      labels=['Baixo', 'Médio', 'Alto'])

# Analisar palavras por categoria
for category in df_featured['price_category'].unique():
    texts = df_featured[df_featured['price_category'] == category]['description']
    print(f"\nPalavras mais comuns - Preço {category}:")
    print(get_top_words(texts))'''))

    nb['cells'].append(nbf.v4.new_markdown_cell('''### 4.3 Sistema de Recomendação'''))

    nb['cells'].append(nbf.v4.new_code_cell('''from sklearn.metrics.pairwise import cosine_similarity

# Preparar features para recomendação
recommend_features = ['year', 'price', 'odometer', 'vehicle_age',
                     'price_per_year', 'price_per_mile']

# Normalizar dados
X_recommend = scaler.fit_transform(df_featured[recommend_features])

# Calcular matriz de similaridade
similarity_matrix = cosine_similarity(X_recommend)

# Função para recomendar veículos similares
def recommend_similar_vehicles(vehicle_id, n=5):
    # Obter índice de similaridade para o veículo
    sim_scores = list(enumerate(similarity_matrix[vehicle_id]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    sim_scores = sim_scores[1:n+1]  # Excluir o próprio veículo
    
    # Obter índices dos veículos similares
    vehicle_indices = [i[0] for i in sim_scores]
    
    return df_featured.iloc[vehicle_indices][['manufacturer', 'model', 'year',
                                            'price', 'odometer']]

# Exemplo de recomendação
print("Exemplo de veículo:")
example_vehicle = df_featured.iloc[0][['manufacturer', 'model', 'year',
                                     'price', 'odometer']]
print(example_vehicle)

print("\nVeículos similares recomendados:")
print(recommend_similar_vehicles(0))'''))

    nb['cells'].append(nbf.v4.new_markdown_cell('''### 4.4 Análise de Competitividade'''))

    nb['cells'].append(nbf.v4.new_code_cell('''# Análise de competitividade por segmento
def analyze_competition(df, segment_column):
    # Calcular métricas de competitividade
    competition = df.groupby(segment_column).agg({
        'price': ['count', 'mean', 'std', 'min', 'max'],
        'manufacturer': 'nunique',
        'model': 'nunique'
    }).round(2)
    
    competition.columns = ['total_listings', 'avg_price', 'price_std',
                         'min_price', 'max_price', 'manufacturers',
                         'models']
    
    # Calcular índice de concentração
    competition['concentration_ratio'] = (
        df.groupby(segment_column)['manufacturer']
        .value_counts()
        .groupby(level=0)
        .head(3)
        .groupby(level=0)
        .sum() / df.groupby(segment_column).size()
    ).round(3)
    
    return competition

# Análise por tipo de veículo
competition_by_type = analyze_competition(df_featured, 'type')
print("Análise de competitividade por tipo de veículo:")
print(competition_by_type)

# Visualizar competitividade
plt.figure(figsize=(12, 6))
competition_by_type['concentration_ratio'].plot(kind='bar')
plt.title('Concentração de Mercado por Tipo de Veículo')
plt.xlabel('Tipo de Veículo')
plt.ylabel('Razão de Concentração')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# Análise de preços relativos
def analyze_price_positioning(df, segment_column):
    # Calcular preço médio do segmento
    segment_avg = df.groupby(segment_column)['price'].transform('mean')
    
    # Calcular posicionamento relativo
    df['price_position'] = (df['price'] - segment_avg) / segment_avg * 100
    
    return df

# Aplicar análise de posicionamento
df_featured = analyze_price_positioning(df_featured, 'type')

# Visualizar posicionamento de preços
plt.figure(figsize=(12, 6))
sns.boxplot(data=df_featured, x='type', y='price_position')
plt.title('Posicionamento de Preços por Tipo de Veículo')
plt.xlabel('Tipo de Veículo')
plt.ylabel('Posição Relativa de Preço (%)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()'''))

    # Save the notebook
    os.makedirs('notebooks', exist_ok=True)
    with open('notebooks/advanced_ml_analysis.ipynb', 'w', encoding='utf-8') as f:
        nbf.write(nb, f)

def main():
    """Creates all notebooks."""
    create_data_cleaning_notebook()
    create_descriptive_analysis_notebook()
    create_sql_analysis_notebook()
    create_advanced_sql_notebook()
    create_ml_analysis_notebook()
    create_advanced_ml_notebook()

if __name__ == "__main__":
    main() 
# Decisões de Limpeza de Dados - Análise de Preços de Veículos

## 1. Problemas Identificados

### 1.1 Preços Extremamente Altos
- **Caso**: Chevrolet Impala 1960 listado por $987,654,321
- **Justificativa para Correção**:
  - Padrão numérico sequencial (987654321) indica erro de entrada
  - Valor excede em mais de 9,000x o preço máximo razoável encontrado ($100,000)
  - Descrição menciona "trade value is higher", mas não justifica o valor exorbitante
  - Veículos clássicos em condições excepcionais não atingem esse valor

### 1.2 Preços Extremamente Baixos
- **Casos**:
  - 3 veículos listados a $1 (Ford F250, Nissan Maxima, Cadillac Escalade)
  - 3 Dodge Charger 2017 listados a $199 (anúncios duplicados)
  - 1 Honda listado a $80
- **Justificativa para Correção**:
  - Descrições revelam preços reais diferentes dos listados
  - Muitos são anúncios de financiamento (ex: "$199 a month")
  - Preços abaixo de $500 são inviáveis para veículos em funcionamento
  - Anúncios duplicados distorcem a análise

## 2. Decisões de Limpeza

### 2.1 Remoção de Registros
- **Registro com preço $987,654,321**
  - Justificativa: Erro óbvio de entrada de dados
  - Impacto: 0.1% do dataset

- **Anúncios duplicados do Dodge Charger**
  - Justificativa: Duplicação artificial de dados
  - Impacto: 0.3% do dataset

### 2.2 Correções de Preços
- **Honda listado a $80**
  - Correção: $800
  - Justificativa: Preço real mencionado na descrição
  - Evidência: "Asking $800" na descrição

- **Cadillac Escalade listado a $1**
  - Correção: $5,500
  - Justificativa: Preço real mencionado na descrição
  - Evidência: "$5,500 OBO" na descrição

### 2.3 Estabelecimento de Limites
- **Limite Inferior**: $500
  - Justificativa: Preço mínimo viável para veículos em funcionamento
  - Exceções: Casos com preços reais claramente documentados na descrição

- **Limite Superior**: $100,000
  - Justificativa: Preço máximo razoável encontrado nos dados normais
  - Exceções: Veículos especiais com documentação adequada

## 3. Impacto das Correções
- Total de registros afetados: 8 (0.8% do dataset)
- Estados afetados: Alabama (AL)
- Anos afetados: 1960, 2002, 2003, 2004, 2012, 2017

## 4. Métricas Pós-Correção
- Média de preços: $19,735
- Mediana de preços: $18,950
- 75% dos carros custam menos que $29,890
- Distribuição mais realista de preços

## 5. Validação
As correções foram validadas através de:
1. Análise de descrições dos anúncios
2. Comparação com preços de mercado
3. Verificação de padrões de duplicação
4. Análise de consistência com outros atributos (ano, condição, quilometragem) 
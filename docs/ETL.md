# Pipeline ETL — fonte canônica

## Visão geral

O entrypoint operacional é:

```bash
python -m src.etl.run_pipeline
# ou, após pip install -e .
run-etl
```

Fluxo implementado:

```text
extract_data()
  → validate_raw()       # Great Expectations opcional; não bloqueante
  → transform_data()
  → validate_clean()     # bloqueante quando Great Expectations está habilitado
  → load_data()          # SQLAlchemy ORM → PostgreSQL
  → OpenLineage events   # opcionais
  → record_etl_run()     # métrica opcional
```

O pipeline retorna código diferente de zero quando conexão, transformação,
validação habilitada ou carga falha. Isso não equivale a exactly-once
distribuído; as garantias transacionais abaixo se limitam às mutações de uma
execução de `load_data()`.

## Componentes

| Caminho | Responsabilidade |
|---|---|
| `src/etl/run_pipeline.py` | Orquestração e entrypoint canônico |
| `src/etl/extract.py` | Leitura e validação básica da entrada CSV |
| `src/etl/transform.py` | Limpeza, enriquecimento e estatísticas |
| `src/etl/ge_validation.py` | Great Expectations opcional |
| `src/etl/load.py` | Upserts, agregados, histórico e transação |
| `src/etl/lineage.py` | OpenLineage opcional |
| `src/database/models.py` | Metadata ORM compartilhado por ETL e API |

Ainda existem utilitários auxiliares e legados em `src/etl/`, mas
`src.etl.run_pipeline` é o fluxo integrado de referência operacional.

## Extração e transformação

`extract_data()` lê o CSV indicado por `RAW_DATA_PATH` com pandas. Quando
presente, `posting_date` é convertido inicialmente para datetime UTC; valores
inválidos tornam-se nulos para tratamento posterior.

A transformação interpreta preço e parcelamento, filtra preços inválidos e
anômalos, calcula idade, padroniza campos textuais e calcula `market_stats` e
agregados por fabricante, estado e ano.

Metadados das etapas são gravados em `logs/metadata/`. Esses arquivos não
participam da transação do PostgreSQL.

## Qualidade de dados

Great Expectations só executa quando o pacote está disponível e `GE_ENABLED`
não é `false`.

- Dados brutos usam `raise_on_failure=False`: falhas são registradas e o
  pipeline continua.
- Dados limpos usam `raise_on_failure=True`: com GE habilitado, suite inválida
  ou erro interrompe o pipeline antes da carga.
- Com GE indisponível ou desabilitado, as duas validações não bloqueiam.

Resultados disponíveis ficam em `gx/uncommitted/validations/` e resumos em
`data/quality/`.

## Carga, identidade e idempotência

### Veículos

`original_id` é a identidade externa canônica. `cars.id` é a chave interna
gerada pelo banco e permanece estável nas cargas subsequentes.

Antes de abrir a sessão de carga, o lote é validado. `original_id` ausente,
nulo, vazio ou duplicado aborta a execução antes das mutações de dados.

O loader:

- insere veículos cujo `original_id` ainda não existe;
- atualiza todas as colunas recebidas de veículos existentes;
- não apaga veículos ausentes do lote;
- não trunca nem recria `cars`.

Duas execuções com a mesma entrada preservam IDs e produzem o mesmo estado
lógico para veículos, histórico e tabelas derivadas.

### Agregados

`market_stats`, `manufacturer_stats`, `state_stats` e `year_stats` são
sincronizadas por suas chaves lógicas. O loader atualiza chaves existentes,
insere novas e remove linhas derivadas que desapareceram do snapshot. IDs das
chaves que permanecem são preservados; reprocessar o mesmo snapshot não duplica
agregados.

## Histórico de preços

`price_history` registra somente mudanças reais de preço em veículos já
existentes. O preço persistido é comparado com o recebido e um evento é criado
apenas quando eles diferem.

- Inserir um veículo não cria automaticamente um evento.
- Repetir uma carga idêntica não cria histórico.
- O histórico existente não é apagado nem reconstruído.
- `car_id` referencia `cars.id` com `ON DELETE CASCADE`.
- `recorded_at` é timezone-aware e possui default no banco.

## Transação e falhas

Upserts de veículos, sincronização das tabelas derivadas e criação de histórico
usam a mesma sessão e um único `commit`, executado depois dessas operações. Uma
exceção anterior ao commit provoca `rollback`, evitando um lote parcial.

A verificação/criação não destrutiva de estruturas com
`Base.metadata.create_all()` ocorre antes da sessão de carga e não pertence à
mesma transação de dados. A garantia também não abrange extração, arquivos de
metadados, eventos externos ou execuções distribuídas.

## Contratos relevantes do schema

### `cars`

- `id`: chave interna `BIGINT`;
- `original_id`: identidade externa com unicidade para valores não nulos;
- `posting_date`: SQL `DATE`, sem horário ou timezone;
- `has_installments`: `BOOLEAN NOT NULL DEFAULT FALSE` após a migration 003.

`posting_date` pode chegar do pandas como `Timestamp` ou `datetime`. A
persistência em `Column(Date)` normaliza o valor para sua parte de data.

### `price_history`

A migration 003 oficializa identidade `BIGINT`, `car_id BIGINT NOT NULL`, FK
para `cars(id)` com cascade, preço, `recorded_at TIMESTAMPTZ` e índice em
`(car_id, price, recorded_at)`. Dados compatíveis existentes são preservados;
órfãos ou estruturas ambíguas fazem a migration abortar.

## Evolução do schema

Execute antes de operar uma versão nova:

```bash
python scripts/run_migration.py
```

O runner envia cada arquivo SQL inteiro em sua própria transação e registra em
`schema_migrations`:

- `filename`: ID lógico como `schemas/<arquivo>.sql` ou
  `migrations/<arquivo>.sql`;
- `checksum_sha256`: checksum do conteúdo aplicado;
- `applied_at`: instante da aplicação;
- `duration_ms`: duração;
- `runner_version`: versão do runner.

Um advisory transaction lock serializa runners concorrentes. A mesma migration
com o mesmo checksum é ignorada; checksum diferente para um ID aplicado causa
erro. Não existe baseline automático: sem histórico, o arquivo é executado e só
depois registrado.

Cada arquivo tem atomicidade própria. Uma falha desfaz aquele arquivo, mas não
migrations anteriores já confirmadas. Os prechecks das migrations 002 e 003
abortam condições inseguras em vez de apagar ou deduplicar dados silenciosamente.

## Lineage e operação da API

OpenLineage está implementado, mas é opcional. Eventos `START`, `COMPLETE` e
`FAIL` são enviados somente quando `openlineage-python` está disponível e
`OPENLINEAGE_URL` está configurada. Sem backend, as operações são no-ops;
falhas de emissão não interrompem a carga. A métrica de sucesso/falha também
possui degradação graciosa.

`/health` é liveness e não depende do banco. `/ready` valida configuração,
executa `SELECT 1` no PostgreSQL e retorna 503 sanitizado quando não está pronto.

## Treinamento e Parquet

Ferramentas do projeto leem e escrevem Parquet pelo pandas; `pyarrow` é
declarado explicitamente como dependência para fornecer suporte a Parquet. O
ETL canônico extrai CSV e carrega PostgreSQL, não grava Parquet por si próprio.

Com `validation=time_series`, `posting_date` é obrigatório, datas inválidas são
descartadas com warning e as linhas são ordenadas cronologicamente. A data serve
para ordenação, não como feature. Cada fold ajusta preprocessing somente em seu
treino; depois da avaliação, preprocessing e modelo finais são ajustados no
dataset completo de treinamento.

## Testes

```bash
python -m pytest \
  tests/unit/test_extract.py \
  tests/unit/test_transform.py \
  tests/unit/test_load.py \
  tests/unit/test_run_pipeline.py -v
```

Testes PostgreSQL reais são opt-in e usam schemas temporários isolados:

```bash
INTEGRATION_DB=1 python -m pytest \
  tests/integration/test_etl_postgresql.py \
  tests/integration/test_migration_002_safety.py \
  tests/integration/test_migration_003_schema_finalization.py \
  tests/integration/test_migration_runner.py -m integration -v
```

Com `INTEGRATION_DB` habilitado, falhas de conexão ou configuração são failures,
não skips.

## Limitações atuais

- Great Expectations e OpenLineage podem estar desabilitados sem impedir o
  pipeline.
- O runner suporta migrations transacionais; `CREATE INDEX CONCURRENTLY` e
  outros comandos incompatíveis com transaction block não são suportados.
- Não existe atomicidade global entre todos os arquivos de migration.
- Constraints específicas de PostgreSQL exigem testes de integração reais;
  SQLite cobre apenas parte dos testes unitários.
- A validação temporal depende de `posting_date` válido e de ordenação antes do
  `TimeSeriesSplit`.
- A transação da carga não abrange arquivos, lineage, telemetria ou sistemas
  externos.

-- Unifica o contrato da tabela cars usado pela API e pelo ETL.
-- Todas as operações são compatíveis com bancos já provisionados.

ALTER TABLE cars ADD COLUMN IF NOT EXISTS original_id TEXT;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS url TEXT;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS region TEXT;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS cylinders TEXT;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS title_status TEXT;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS vin TEXT;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS size TEXT;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS price_original DOUBLE PRECISION;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS has_installments BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS monthly_payment DOUBLE PRECISION;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS down_payment DOUBLE PRECISION;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS installments INTEGER;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;
ALTER TABLE market_stats ADD COLUMN IF NOT EXISTS state TEXT;

-- Impede escrita concorrente entre os prechecks e a criação dos índices.
LOCK TABLE cars, market_stats IN SHARE MODE;

-- Falha de forma não destrutiva se a identidade externa já estiver duplicada.
-- A mensagem é fixa para não expor IDs existentes nos logs.
SELECT CAST(
    CASE WHEN EXISTS (
        SELECT 1
        FROM cars
        WHERE original_id IS NOT NULL
        GROUP BY original_id
        HAVING COUNT(*) > 1
    ) THEN 'MIGRATION_002_PRECHECK_FAILED_CARS_DUPLICATE_ORIGINAL_ID'
      ELSE '1'
    END AS INTEGER
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_cars_original_id
    ON cars (original_id) WHERE original_id IS NOT NULL;

-- NULL impediria que o índice único representasse a identidade lógica esperada.
SELECT CAST(
    CASE WHEN EXISTS (
        SELECT 1
        FROM market_stats
        WHERE manufacturer IS NULL OR model IS NULL OR year IS NULL
    ) THEN 'MIGRATION_002_PRECHECK_FAILED_MARKET_STATS_NULL_KEY'
      ELSE '1'
    END AS INTEGER
);

-- Não escolhe vencedor nem apaga estatísticas: conflitos exigem remediação auditável.
SELECT CAST(
    CASE WHEN EXISTS (
        SELECT 1
        FROM market_stats
        GROUP BY manufacturer, model, year
        HAVING COUNT(*) > 1
    ) THEN 'MIGRATION_002_PRECHECK_FAILED_MARKET_STATS_DUPLICATE_KEY'
      ELSE '1'
    END AS INTEGER
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_market_stats_main
    ON market_stats (manufacturer, model, year);

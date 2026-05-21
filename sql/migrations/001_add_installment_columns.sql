-- Migration 001: adicionar colunas de parcelamento caso a tabela já exista
-- sem as colunas (upgrade de schema incremental)

ALTER TABLE cars ADD COLUMN IF NOT EXISTS price_original    FLOAT;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS has_installments  BOOLEAN DEFAULT FALSE;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS monthly_payment   FLOAT;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS down_payment      FLOAT;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS installments      INTEGER;

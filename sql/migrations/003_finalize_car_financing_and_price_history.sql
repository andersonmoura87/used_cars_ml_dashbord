-- Finaliza a semântica de financiamento e versiona o histórico de preços.
-- A migration é deliberadamente não destrutiva e roda na transação do runner.

ALTER TABLE cars
    ADD COLUMN IF NOT EXISTS has_installments BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS price_history (
    id BIGSERIAL PRIMARY KEY,
    car_id BIGINT NOT NULL,
    price DOUBLE PRECISION,
    recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

LOCK TABLE cars, price_history IN SHARE ROW EXCLUSIVE MODE;

-- Tipos desconhecidos não são convertidos implicitamente: exigem remediação auditável.
DO $$
DECLARE
    column_type TEXT;
    id_sequence TEXT;
BEGIN
    SELECT format_type(attribute.atttypid, attribute.atttypmod)
      INTO column_type
      FROM pg_attribute AS attribute
     WHERE attribute.attrelid = 'cars'::regclass
       AND attribute.attname = 'has_installments'
       AND NOT attribute.attisdropped;
    IF column_type IS DISTINCT FROM 'boolean' THEN
        RAISE EXCEPTION 'MIGRATION_003_PRECHECK_FAILED_HAS_INSTALLMENTS_TYPE';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM (VALUES
              ('id', ARRAY['integer', 'bigint']::TEXT[]),
              ('car_id', ARRAY['integer', 'bigint']::TEXT[]),
              ('price', ARRAY['real', 'double precision']::TEXT[]),
              ('recorded_at', ARRAY['timestamp with time zone']::TEXT[])
          ) AS expected(column_name, allowed_types)
         WHERE NOT EXISTS (
             SELECT 1
               FROM pg_attribute AS attribute
              WHERE attribute.attrelid = 'price_history'::regclass
                AND attribute.attname = expected.column_name
                AND NOT attribute.attisdropped
                AND format_type(attribute.atttypid, attribute.atttypmod)
                    = ANY(expected.allowed_types)
         )
    ) THEN
        RAISE EXCEPTION 'MIGRATION_003_PRECHECK_FAILED_PRICE_HISTORY_COLUMNS_OR_TYPES';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conrelid = 'price_history'::regclass
           AND contype = 'p'
           AND conkey = ARRAY[
               (SELECT attnum FROM pg_attribute
                 WHERE attrelid = 'price_history'::regclass AND attname = 'id')
           ]::SMALLINT[]
    ) THEN
        RAISE EXCEPTION 'MIGRATION_003_PRECHECK_FAILED_PRICE_HISTORY_PRIMARY_KEY';
    END IF;

    IF EXISTS (SELECT 1 FROM price_history WHERE car_id IS NULL) THEN
        RAISE EXCEPTION 'MIGRATION_003_PRECHECK_FAILED_PRICE_HISTORY_NULL_CAR_ID';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM price_history AS history
          LEFT JOIN cars ON cars.id = history.car_id
         WHERE cars.id IS NULL
    ) THEN
        RAISE EXCEPTION 'MIGRATION_003_PRECHECK_FAILED_PRICE_HISTORY_ORPHAN_CAR_ID';
    END IF;

    -- Uma FK incompatível não é removida silenciosamente.
    IF EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conrelid = 'price_history'::regclass
           AND contype = 'f'
           AND conkey = ARRAY[
               (SELECT attnum FROM pg_attribute
                 WHERE attrelid = 'price_history'::regclass AND attname = 'car_id')
           ]::SMALLINT[]
           AND NOT (
               confrelid = 'cars'::regclass
               AND confkey = ARRAY[
                   (SELECT attnum FROM pg_attribute
                     WHERE attrelid = 'cars'::regclass AND attname = 'id')
               ]::SMALLINT[]
               AND confdeltype = 'c'
           )
    ) THEN
        RAISE EXCEPTION 'MIGRATION_003_PRECHECK_FAILED_PRICE_HISTORY_FOREIGN_KEY';
    END IF;

    SELECT pg_get_serial_sequence('price_history', 'id') INTO id_sequence;
    IF id_sequence IS NULL AND NOT EXISTS (
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = 'price_history'
           AND column_name = 'id'
           AND is_identity = 'YES'
    ) THEN
        RAISE EXCEPTION 'MIGRATION_003_PRECHECK_FAILED_PRICE_HISTORY_ID_GENERATOR';
    END IF;
END
$$;

-- INTEGER -> BIGINT e REAL -> DOUBLE PRECISION são ampliações sem perda.
-- Uma FK correta existente é removida apenas durante a ampliação de car_id e
-- recriada na mesma transação; qualquer falha restaura a constraint original.
DO $$
DECLARE
    constraint_name NAME;
BEGIN
    IF (
        SELECT format_type(attribute.atttypid, attribute.atttypmod)
          FROM pg_attribute AS attribute
         WHERE attribute.attrelid = 'price_history'::regclass
           AND attribute.attname = 'car_id'
           AND NOT attribute.attisdropped
    ) = 'integer' THEN
        FOR constraint_name IN
            SELECT conname
              FROM pg_constraint
             WHERE conrelid = 'price_history'::regclass
               AND contype = 'f'
               AND conkey = ARRAY[
                   (SELECT attnum FROM pg_attribute
                     WHERE attrelid = 'price_history'::regclass AND attname = 'car_id')
               ]::SMALLINT[]
               AND confrelid = 'cars'::regclass
               AND confkey = ARRAY[
                   (SELECT attnum FROM pg_attribute
                     WHERE attrelid = 'cars'::regclass AND attname = 'id')
               ]::SMALLINT[]
               AND confdeltype = 'c'
        LOOP
            EXECUTE 'ALTER TABLE price_history DROP CONSTRAINT '
                || quote_ident(constraint_name);
        END LOOP;
    END IF;
END
$$;

ALTER TABLE price_history ALTER COLUMN id TYPE BIGINT;
ALTER TABLE price_history ALTER COLUMN car_id TYPE BIGINT;
ALTER TABLE price_history ALTER COLUMN price TYPE DOUBLE PRECISION;
ALTER TABLE price_history ALTER COLUMN car_id SET NOT NULL;
ALTER TABLE price_history ALTER COLUMN recorded_at SET DEFAULT CURRENT_TIMESTAMP;

DO $$
DECLARE
    id_sequence TEXT;
BEGIN
    SELECT pg_get_serial_sequence('price_history', 'id') INTO id_sequence;
    IF id_sequence IS NOT NULL THEN
        EXECUTE 'ALTER SEQUENCE '
            || (id_sequence::regclass)::TEXT
            || ' AS BIGINT';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conrelid = 'price_history'::regclass
           AND contype = 'f'
           AND conkey = ARRAY[
               (SELECT attnum FROM pg_attribute
                 WHERE attrelid = 'price_history'::regclass AND attname = 'car_id')
           ]::SMALLINT[]
           AND confrelid = 'cars'::regclass
           AND confkey = ARRAY[
               (SELECT attnum FROM pg_attribute
                 WHERE attrelid = 'cars'::regclass AND attname = 'id')
           ]::SMALLINT[]
           AND confdeltype = 'c'
    ) THEN
        ALTER TABLE price_history
            ADD CONSTRAINT fk_price_history_car_id_cars
            FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE;
    END IF;
END
$$;

-- NULL histórico significa que não havia evidência de parcelamento. A política
-- persistida converge esse estado para FALSE sem tocar em TRUE ou FALSE existentes.
UPDATE cars SET has_installments = FALSE WHERE has_installments IS NULL;
ALTER TABLE cars ALTER COLUMN has_installments SET DEFAULT FALSE;
ALTER TABLE cars ALTER COLUMN has_installments SET NOT NULL;

DO $$
DECLARE
    named_index_matches BOOLEAN;
    equivalent_index_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
          FROM pg_index AS index_info
          JOIN pg_class AS index_class ON index_class.oid = index_info.indexrelid
         WHERE index_info.indrelid = 'price_history'::regclass
           AND index_class.relname = 'idx_car_price_date'
           AND ARRAY(
               SELECT attribute.attname
                 FROM unnest(index_info.indkey::SMALLINT[]) WITH ORDINALITY
                      AS key_column(attnum, position)
                 JOIN pg_attribute AS attribute
                   ON attribute.attrelid = index_info.indrelid
                  AND attribute.attnum = key_column.attnum
                ORDER BY key_column.position
           ) = ARRAY['car_id', 'price', 'recorded_at']::NAME[]
           AND index_info.indpred IS NULL
           AND index_info.indexprs IS NULL
    ) INTO named_index_matches;

    IF to_regclass('idx_car_price_date') IS NOT NULL AND NOT named_index_matches THEN
        RAISE EXCEPTION 'MIGRATION_003_PRECHECK_FAILED_PRICE_HISTORY_INDEX_NAME';
    END IF;

    SELECT EXISTS (
        SELECT 1
          FROM pg_index AS index_info
         WHERE index_info.indrelid = 'price_history'::regclass
           AND ARRAY(
               SELECT attribute.attname
                 FROM unnest(index_info.indkey::SMALLINT[]) WITH ORDINALITY
                      AS key_column(attnum, position)
                 JOIN pg_attribute AS attribute
                   ON attribute.attrelid = index_info.indrelid
                  AND attribute.attnum = key_column.attnum
                ORDER BY key_column.position
           ) = ARRAY['car_id', 'price', 'recorded_at']::NAME[]
           AND index_info.indpred IS NULL
           AND index_info.indexprs IS NULL
    ) INTO equivalent_index_exists;

    IF NOT equivalent_index_exists THEN
        CREATE INDEX idx_car_price_date
            ON price_history (car_id, price, recorded_at);
    END IF;
END
$$;

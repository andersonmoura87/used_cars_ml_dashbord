-- Schema principal do projeto used_cars_ml_dashbord
-- Executado antes das migrations pelo run_migration.py

CREATE TABLE IF NOT EXISTS cars (
    id              BIGSERIAL PRIMARY KEY,
    original_id     TEXT UNIQUE,
    url             TEXT,
    region          TEXT,
    price           FLOAT,
    year            INTEGER,
    manufacturer    TEXT,
    model           TEXT,
    condition       TEXT,
    cylinders       TEXT,
    fuel            TEXT,
    odometer        FLOAT,
    title_status    TEXT,
    transmission    TEXT,
    vin             TEXT,
    drive           TEXT,
    size            TEXT,
    type            TEXT,
    paint_color     TEXT,
    state           TEXT,
    latitude        FLOAT,
    longitude       FLOAT,
    posting_date    DATE,
    vehicle_age     INTEGER,
    -- Financing fields
    price_original  FLOAT,
    has_installments BOOLEAN DEFAULT FALSE,
    monthly_payment FLOAT,
    down_payment    FLOAT,
    installments    INTEGER
);

CREATE INDEX IF NOT EXISTS idx_cars_manufacturer  ON cars (manufacturer);
CREATE INDEX IF NOT EXISTS idx_cars_state         ON cars (state);
CREATE INDEX IF NOT EXISTS idx_cars_year          ON cars (year);
CREATE INDEX IF NOT EXISTS idx_cars_price         ON cars (price);

CREATE TABLE IF NOT EXISTS manufacturer_stats (
    id               SERIAL PRIMARY KEY,
    manufacturer     TEXT UNIQUE,
    total_listings   INTEGER,
    avg_price        FLOAT,
    min_price        FLOAT,
    max_price        FLOAT,
    avg_year         FLOAT,
    total_financed   INTEGER,
    avg_monthly_payment FLOAT,
    avg_down_payment    FLOAT,
    avg_installments    FLOAT
);

CREATE TABLE IF NOT EXISTS state_stats (
    id               SERIAL PRIMARY KEY,
    state            TEXT UNIQUE,
    total_listings   INTEGER,
    avg_price        FLOAT,
    min_price        FLOAT,
    max_price        FLOAT,
    total_financed   INTEGER,
    avg_monthly_payment FLOAT,
    avg_down_payment    FLOAT,
    avg_installments    FLOAT
);

CREATE TABLE IF NOT EXISTS year_stats (
    id               SERIAL PRIMARY KEY,
    year             INTEGER UNIQUE,
    total_listings   INTEGER,
    avg_price        FLOAT,
    min_price        FLOAT,
    max_price        FLOAT,
    total_financed   INTEGER,
    avg_monthly_payment FLOAT,
    avg_down_payment    FLOAT,
    avg_installments    FLOAT
);

CREATE TABLE IF NOT EXISTS market_stats (
    id              SERIAL PRIMARY KEY,
    manufacturer    TEXT,
    model           TEXT,
    year            INTEGER,
    avg_price       FLOAT,
    median_price    FLOAT,
    min_price       FLOAT,
    max_price       FLOAT,
    total_listings  INTEGER,
    days_listed     INTEGER,
    calculated_at   TIMESTAMPTZ,
    UNIQUE (manufacturer, model, year)
);

-- View para o dashboard Streamlit (src/app.py)
CREATE OR REPLACE VIEW cars_cleaned AS
SELECT
    manufacturer, model, year, price, odometer, fuel,
    condition, state, region, latitude, longitude, posting_date,
    (EXTRACT(YEAR FROM NOW()) - year)::INTEGER AS vehicle_age,
    transmission, drive, type, paint_color
FROM cars
WHERE price > 0
  AND year >= 1990
  AND posting_date IS NOT NULL;

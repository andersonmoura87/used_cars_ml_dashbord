-- Cria o banco de dados do MLflow se não existir.
-- Executado antes do 001_create_tables.sql pelo run_migration.py.
-- Nota: precisa ser conectado ao banco 'postgres' (default) para criar outro banco.
SELECT 'CREATE DATABASE mlflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mlflow')\gexec

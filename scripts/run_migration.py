#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para executar migrações do banco de dados.
"""

import hashlib
import logging
import sys
import time
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.database.connection import create_db_engine  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

RUNNER_VERSION = "1"
_ADVISORY_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"used_cars_ml_dashbord:migrations").digest()[:8],
    byteorder="big",
    signed=True,
)


class MigrationChecksumMismatch(RuntimeError):
    """Uma migration já aplicada foi modificada no disco."""


def _migration_content(migration_file: Path) -> tuple[str, str]:
    raw = migration_file.read_bytes()
    return raw.decode("utf-8-sig"), hashlib.sha256(raw).hexdigest()


def _migration_identifier(migration_file: Path) -> str:
    """Retorna um ID portátil, sem incluir o caminho absoluto da máquina."""
    resolved = migration_file.resolve()
    for directory in ("schemas", "migrations"):
        root = (ROOT / "sql" / directory).resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError:
            continue
        return f"{directory}/{relative.as_posix()}"
    return f"external/{migration_file.name}"


def _ensure_history_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                checksum_sha256 CHAR(64) NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                duration_ms DOUBLE PRECISION NOT NULL,
                runner_version TEXT NOT NULL
            )
            """
        )
    )


def get_db_connection():
    """
    Create database connection from environment variables.
    """
    return create_db_engine()


def run_migration(engine, migration_file):
    """
    Executa uma migration transacional uma única vez e registra seu checksum.

    Não existe baseline automático: se ``schema_migrations`` ainda não existir,
    o arquivo é executado normalmente e só então registrado. O runner não infere
    o estado prévio do banco nem insere checksums retroativamente.
    """
    migration_file = Path(migration_file)
    filename = _migration_identifier(migration_file)
    sql, checksum = _migration_content(migration_file)
    logger.info("Running migration: %s", migration_file)

    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY})
            _ensure_history_table(conn)
            applied_checksum = conn.execute(
                text(
                    "SELECT checksum_sha256 FROM schema_migrations "
                    "WHERE filename = :filename"
                ),
                {"filename": filename},
            ).scalar_one_or_none()

            if applied_checksum is not None:
                if applied_checksum.strip() != checksum:
                    raise MigrationChecksumMismatch(
                        f"Applied migration was modified: {filename}"
                    )
                logger.info("Migration already applied; skipping: %s", filename)
                return False

            started_at = time.perf_counter()
            conn.exec_driver_sql(sql)
            duration_ms = (time.perf_counter() - started_at) * 1000
            conn.execute(
                text(
                    "INSERT INTO schema_migrations "
                    "(filename, checksum_sha256, duration_ms, runner_version) "
                    "VALUES (:filename, :checksum, :duration_ms, :runner_version)"
                ),
                {
                    "filename": filename,
                    "checksum": checksum,
                    "duration_ms": duration_ms,
                    "runner_version": RUNNER_VERSION,
                },
            )

        logger.info("Migration completed: %s", migration_file)
        return True
    except Exception as exc:
        logger.error("Error running migration %s: %s", migration_file, exc)
        raise


def main():
    """
    Run all database migrations.
    """
    try:
        logger.info("Starting database migration")

        # Get database connection
        engine = get_db_connection()

        # Get migration files
        migrations_dir = Path(__file__).parent.parent / 'sql' / 'migrations'
        schema_dir = Path(__file__).parent.parent / 'sql' / 'schemas'

        if not migrations_dir.exists():
            logger.error(f"Migrations directory not found: {migrations_dir}")
            sys.exit(1)

        if not schema_dir.exists():
            logger.error(f"Schema directory not found: {schema_dir}")
            sys.exit(1)

        # Schemas SQL também são rastreados e não são reaplicados silenciosamente.
        # 000_create_mlflow_db.sql contém \gexec, uma meta-instrução exclusiva
        # do psql usada pelo container MLflow; não pode ser executada via SQLAlchemy.
        schema_files = [
            path for path in sorted(schema_dir.glob('*.sql'))
            if path.name != '000_create_mlflow_db.sql'
        ]
        for schema_file in schema_files:
            run_migration(engine, schema_file)

        # Run migrations in order
        migration_files = sorted(migrations_dir.glob('*.sql'))
        for migration_file in migration_files:
            run_migration(engine, migration_file)

        logger.info("Database migration completed successfully")

    except Exception as e:
        logger.error(f"Database migration failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

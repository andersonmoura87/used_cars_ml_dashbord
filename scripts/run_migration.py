#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para executar migrações do banco de dados.
"""

import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database connection settings
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "used_cars")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# Create database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def get_db_connection():
    """
    Create database connection from environment variables.
    """
    return create_engine(DATABASE_URL)

def run_migration(engine, migration_file):
    """
    Execute a SQL migration file.
    """
    logger.info(f"Running migration: {migration_file}")
    
    try:
        with open(migration_file, 'r', encoding='utf-8-sig') as f:
            sql = f.read()
            
        with engine.connect() as conn:
            # Set client encoding to UTF-8
            conn.execute(text("SET client_encoding TO 'UTF8';"))
            
            # Split SQL into individual statements
            statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
            
            # Execute each statement
            for statement in statements:
                try:
                    logger.info(f"Executing: {statement[:100]}...")
                    conn.execute(text(statement))
                except Exception as e:
                    # Log the error but continue with other statements
                    if "already exists" in str(e):
                        logger.warning(f"Object already exists: {str(e)}")
                    else:
                        logger.error(f"Error executing statement: {str(e)}")
                        raise
            
            conn.commit()
            
        logger.info(f"Migration completed: {migration_file}")
        
    except Exception as e:
        logger.error(f"Error running migration {migration_file}: {str(e)}")
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
        
        # Run schema first
        schema_files = sorted(schema_dir.glob('*.sql'))
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
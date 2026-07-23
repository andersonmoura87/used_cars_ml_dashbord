from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection settings — sem senha default (risco de produção)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "used_cars")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

if not DB_PASSWORD:
    _env = os.getenv("ENVIRONMENT", "development").lower()
    if _env in ("production", "staging"):
        raise RuntimeError(
            "DB_PASSWORD não definido — obrigatório em staging/production. "
            "Ver docs/SECRETS.md ou: python scripts/check_secrets.py -e production"
        )
    # development: permite vazio apenas se DATABASE_URL completo for usado depois;
    # ainda assim evita o default inseguro "postgres"
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "DB_PASSWORD vazio — defina no .env (nunca use 'postgres' em staging/prod)"
    )

# Create database URL
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create database engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    user     = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    host     = os.environ.get("DB_HOST", "localhost")
    port     = os.environ.get("DB_PORT", "5432")
    name     = os.environ.get("DB_NAME", "used_cars")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def create_db_engine():
    """
    Cria e retorna uma Engine SQLAlchemy com pool configurável via env vars.

    Low-FIX: limites de pool via variáveis de ambiente para evitar esgotamento
    de conexões em produção.
    """
    pool_size    = int(os.environ.get("DB_POOL_SIZE",    "5"))
    max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "10"))
    pool_timeout = int(os.environ.get("DB_POOL_TIMEOUT", "30"))
    pool_recycle = int(os.environ.get("DB_POOL_RECYCLE", "1800"))

    try:
        engine = create_engine(
            get_database_url(),
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,   # detecta conexões mortas antes de usar
            connect_args={
                "client_encoding": "utf8",
                "options": "-c client_encoding=utf8",
                # statement_timeout em ms — protege contra queries longas
                "options": (
                    "-c client_encoding=utf8 "
                    f"-c statement_timeout={os.environ.get('DB_STATEMENT_TIMEOUT_MS', '30000')}"
                ),
            },
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Engine do banco de dados criada (pool_size=%d, max_overflow=%d)", pool_size, max_overflow)
        return engine
    except SQLAlchemyError as exc:
        logger.error("Erro ao criar engine do banco de dados: %s", exc)
        raise


# Sessão reutilizável (singleton por processo)
_engine = None
_SessionFactory = None


def get_session_factory() -> sessionmaker:
    global _engine, _SessionFactory
    if _SessionFactory is None:
        _engine = create_db_engine()
        _SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _SessionFactory


def get_db_session() -> Session:
    """Retorna uma sessão do banco. Responsabilidade do caller fechar com session.close()."""
    return get_session_factory()()


def get_db_connection():
    """Alias para compatibilidade retroativa com scripts antigos."""
    return create_db_engine()


def test_connection() -> bool:
    try:
        engine = create_db_engine()
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version();")).scalar()
        logger.info("Conectado ao PostgreSQL. Versão: %s", version)
        return True
    except SQLAlchemyError as exc:
        logger.error("Erro ao testar conexão: %s", exc)
        return False

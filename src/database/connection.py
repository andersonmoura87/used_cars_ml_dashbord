from __future__ import annotations

import logging
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseConfigurationError(RuntimeError):
    """Configuração obrigatória do banco ausente ou inválida."""


def validate_database_config(environment: str | None = None) -> None:
    """Valida configuração sem abrir conexão e sem incluir valores em erros."""
    environment = (environment or os.getenv("ENVIRONMENT", "development")).lower()
    required = ["DB_USER", "DB_PASSWORD"]
    if environment in {"production", "staging"}:
        required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]

    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise DatabaseConfigurationError(
            "Missing required database configuration: " + ", ".join(missing)
        )

    port = os.getenv("DB_PORT", "5432")
    try:
        port_number = int(port)
    except ValueError as exc:
        raise DatabaseConfigurationError("Invalid database configuration: DB_PORT") from exc
    if not 1 <= port_number <= 65535:
        raise DatabaseConfigurationError("Invalid database configuration: DB_PORT")


def get_database_url() -> str:
    validate_database_config()
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "used_cars")
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{name}"
    )


def create_db_engine():
    """
    Cria e retorna uma Engine SQLAlchemy com pool configurável via env vars.

    Low-FIX: limites de pool via variáveis de ambiente para evitar esgotamento
    de conexões em produção.
    """
    try:
        pool_size = int(os.environ.get("DB_POOL_SIZE", "5"))
        max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "10"))
        pool_timeout = int(os.environ.get("DB_POOL_TIMEOUT", "30"))
        pool_recycle = int(os.environ.get("DB_POOL_RECYCLE", "1800"))
        engine = create_engine(
            get_database_url(),
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,   # detecta conexões mortas antes de usar
            connect_args={
                "client_encoding": "utf8",
                # statement_timeout em ms — protege contra queries longas
                "options": (
                    "-c client_encoding=utf8 "
                    f"-c statement_timeout={os.environ.get('DB_STATEMENT_TIMEOUT_MS', '30000')}"
                ),
            },
        )
        logger.info("Engine do banco de dados criada (pool_size=%d, max_overflow=%d)", pool_size, max_overflow)
        return engine
    except (DatabaseConfigurationError, SQLAlchemyError, ValueError) as exc:
        logger.error("Falha ao criar engine do banco (%s)", type(exc).__name__)
        raise


# Sessão reutilizável (singleton por processo)
_engine = None
_SessionFactory = None


def get_db_engine():
    """Retorna a engine compartilhada, criando-a apenas no primeiro uso."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_db_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _SessionFactory


def get_db_session() -> Session:
    """Retorna uma sessão do banco. Responsabilidade do caller fechar com session.close()."""
    return get_session_factory()()


def get_db_connection():
    """Alias para compatibilidade retroativa com scripts antigos."""
    return create_db_engine()


def check_database_readiness() -> bool:
    """Valida configuração e conectividade real usando a engine compartilhada."""
    validate_database_config()
    with get_db_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


def test_connection() -> bool:
    try:
        return check_database_readiness()
    except (DatabaseConfigurationError, SQLAlchemyError):
        logger.error("Falha no teste de conexão com o banco")
        return False

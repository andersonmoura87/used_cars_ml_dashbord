"""Dependência de sessão da API usando a infraestrutura canônica do banco."""

from src.database.connection import get_db_session
from src.database.models import Base

__all__ = ("Base", "get_db")


def get_db():
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()

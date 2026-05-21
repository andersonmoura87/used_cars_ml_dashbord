"""
Módulo compartilhado de carregamento de dados para o dashboard.

Todas as páginas importam daqui — elimina os 6 load_data() duplicados.
Hierarquia de fontes:
  1. data/processed/cars_abt.csv  (padrão local, mais rápido)
  2. data/cleansed/used_cars.parquet
  3. PostgreSQL via variáveis de ambiente DB_*
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── caminhos ──────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
_CSV_PATH = _ROOT / "data" / "processed" / "cars_abt.csv"
_PARQUET_PATH = _ROOT / "data" / "cleansed" / "used_cars.parquet"


def _db_engine():
    """Cria engine SQLAlchemy apenas se variáveis de ambiente estiverem definidas."""
    from sqlalchemy import create_engine

    host = os.getenv("DB_HOST")
    if not host:
        return None
    return create_engine(
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{host}:{os.getenv('DB_PORT', 5432)}/{os.getenv('DB_NAME')}",
        connect_args={"client_encoding": "utf8"},
    )


@st.cache_data(ttl=3600, show_spinner="Carregando dados...")
def load_data() -> pd.DataFrame | None:
    """
    Carrega o dataset principal com fallback automático entre fontes.
    Retorna None e exibe st.error se nenhuma fonte estiver disponível.
    """
    # 1. CSV local
    if _CSV_PATH.exists():
        try:
            df = pd.read_csv(_CSV_PATH)
            _ensure_columns(df)
            return df
        except Exception as exc:
            st.warning(f"CSV indisponível ({exc}), tentando parquet…")

    # 2. Parquet local
    if _PARQUET_PATH.exists():
        try:
            df = pd.read_parquet(_PARQUET_PATH)
            _ensure_columns(df)
            return df
        except Exception as exc:
            st.warning(f"Parquet indisponível ({exc}), tentando banco…")

    # 3. PostgreSQL
    engine = _db_engine()
    if engine:
        try:
            df = pd.read_sql(
                """
                SELECT manufacturer, model, year, price, odometer, fuel,
                       condition, state, region, latitude, longitude,
                       posting_date, vehicle_age, transmission, drive,
                       type, paint_color
                FROM cars_cleaned
                WHERE price > 0 AND year >= 1990
                """,
                engine,
                parse_dates=["posting_date"],
            )
            _ensure_columns(df)
            return df
        except Exception as exc:
            st.error(f"Banco de dados indisponível: {exc}")
            return None

    st.error(
        "Nenhuma fonte de dados encontrada.\n\n"
        "Verifique se existe `data/processed/cars_abt.csv` ou configure as "
        "variáveis de ambiente DB_* no arquivo `.env`."
    )
    return None


def _ensure_columns(df: pd.DataFrame) -> None:
    """Garante colunas mínimas e tipos corretos."""
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
    if "odometer" in df.columns:
        df["odometer"] = pd.to_numeric(df["odometer"], errors="coerce")
    if "posting_date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["posting_date"]):
        df["posting_date"] = pd.to_datetime(df["posting_date"], errors="coerce")
    # vehicle_age derivado
    if "vehicle_age" not in df.columns and "year" in df.columns:
        import datetime
        df["vehicle_age"] = datetime.date.today().year - df["year"]


def sidebar_filters(df: pd.DataFrame, show_region: bool = False) -> pd.DataFrame:
    """
    Renderiza filtros padrão na sidebar e retorna DataFrame filtrado.
    Reutilizável em todas as páginas.
    """
    st.sidebar.header("Filtros")

    manufacturers = sorted(df["manufacturer"].dropna().unique())
    sel_mfr = st.sidebar.multiselect("Fabricante", manufacturers, default=[])

    year_min, year_max = int(df["year"].min()), int(df["year"].max())
    year_range = st.sidebar.slider("Ano", year_min, year_max, (year_min, year_max))

    price_min, price_max = float(df["price"].min()), float(df["price"].quantile(0.99))
    price_range = st.sidebar.slider(
        "Faixa de Preço ($)",
        price_min, price_max,
        (price_min, price_max),
        format="$%.0f",
    )

    mask = (
        df["year"].between(*year_range)
        & df["price"].between(*price_range)
    )
    if sel_mfr:
        mask &= df["manufacturer"].isin(sel_mfr)

    if show_region and "region" in df.columns:
        regions = sorted(df["region"].dropna().unique())
        sel_regions = st.sidebar.multiselect("Região", regions, default=[])
        if sel_regions:
            mask &= df["region"].isin(sel_regions)

    filtered = df[mask]
    st.sidebar.markdown(f"**{len(filtered):,}** carros selecionados")
    return filtered

"""Página Comprador — busca e comparação de veículos."""
import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from _loader import load_data

st.set_page_config(page_title="Comprador", page_icon="🛒", layout="wide")

st.title("Comprador")
st.caption("Encontre o carro ideal para você")

df = load_data()
if df is None:
    st.stop()

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Suas preferências")

    c1, c2 = st.columns(2)
    with c1:
        manufacturers = sorted(df["manufacturer"].dropna().unique())
        sel_mfr = st.selectbox("Fabricante", ["Todos"] + manufacturers)
        fuel_types = sorted(df["fuel"].dropna().unique())
        sel_fuel = st.selectbox("Combustível", ["Todos"] + fuel_types)

    with c2:
        trans_types = sorted(df["transmission"].dropna().unique())
        sel_trans = st.selectbox("Transmissão", ["Todos"] + trans_types)
        conditions = sorted(df["condition"].dropna().unique())
        sel_cond = st.selectbox("Condição", ["Todos"] + conditions)

    st.subheader("Faixas")
    price_range = st.slider(
        "Preço ($)",
        int(df["price"].min()), int(df["price"].max()),
        (int(df["price"].min()), int(df["price"].quantile(0.75))),
    )
    year_range = st.slider(
        "Ano",
        int(df["year"].min()), int(df["year"].max()),
        (int(df["year"].quantile(0.25)), int(df["year"].max())),
    )
    odo_range = st.slider(
        "Quilometragem",
        int(df["odometer"].min()), int(df["odometer"].max()),
        (int(df["odometer"].min()), int(df["odometer"].quantile(0.75))),
    )

# ── filtros ───────────────────────────────────────────────────────────────────
fdf = df.copy()
if sel_mfr != "Todos":
    fdf = fdf[fdf["manufacturer"] == sel_mfr]
if sel_fuel != "Todos":
    fdf = fdf[fdf["fuel"] == sel_fuel]
if sel_trans != "Todos":
    fdf = fdf[fdf["transmission"] == sel_trans]
if sel_cond != "Todos":
    fdf = fdf[fdf["condition"] == sel_cond]

fdf = fdf[
    fdf["price"].between(*price_range)
    & fdf["year"].between(*year_range)
    & fdf["odometer"].between(*odo_range)
]

# ── métricas ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Carros encontrados", f"{len(fdf):,}")
c2.metric("Preço médio", f"${fdf['price'].mean():,.2f}" if len(fdf) else "—")
c3.metric("Ano médio", f"{fdf['year'].mean():.0f}" if len(fdf) else "—")
c4.metric("Km média", f"{fdf['odometer'].mean():,.0f}" if len(fdf) else "—")

if fdf.empty:
    st.warning("Nenhum carro encontrado com os filtros selecionados.")
    st.stop()

# ── gráficos ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    fig = px.histogram(
        fdf, x="price",
        title="Distribuição de Preços",
        labels={"price": "Preço ($)", "count": "Quantidade"},
        nbins=40,
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig = px.scatter(
        fdf, x="year", y="price", color="manufacturer",
        title="Preço vs. Ano",
        labels={"year": "Ano", "price": "Preço ($)"},
        opacity=0.6,
    )
    st.plotly_chart(fig, use_container_width=True)

col1, col2 = st.columns(2)

with col1:
    fig = px.scatter(
        fdf, x="odometer", y="price", color="condition",
        title="Preço vs. Quilometragem",
        labels={"odometer": "Quilometragem", "price": "Preço ($)"},
        opacity=0.5,
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    avg_by_mfr = (
        fdf.groupby("manufacturer")["price"]
        .mean()
        .sort_values(ascending=False)
        .head(15)
        .reset_index()
    )
    fig = px.bar(
        avg_by_mfr, x="price", y="manufacturer", orientation="h",
        title="Preço Médio por Fabricante (top 15)",
        labels={"price": "Preço Médio ($)", "manufacturer": ""},
    )
    st.plotly_chart(fig, use_container_width=True)

# ── tabela ────────────────────────────────────────────────────────────────────
st.subheader("Lista de carros")
display_cols = ["manufacturer", "model", "year", "price", "odometer", "condition", "fuel", "transmission"]
available = [c for c in display_cols if c in fdf.columns]
out = fdf[available].rename(columns={
    "manufacturer": "Fabricante", "model": "Modelo", "year": "Ano",
    "price": "Preço ($)", "odometer": "Km", "condition": "Condição",
    "fuel": "Combustível", "transmission": "Câmbio",
}).copy()
out["Preço ($)"] = out["Preço ($)"].map("${:,.2f}".format)
out["Km"] = out["Km"].map("{:,.0f}".format)
st.dataframe(out.sort_values("Preço ($)"), use_container_width=True, height=380)

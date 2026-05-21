"""
Home — CarMarket Analytics
Ponto de entrada único do dashboard Streamlit multipage.
Execute: streamlit run dashboard/Home.py
"""
import streamlit as st
from pathlib import Path
import sys

# Garante que o pacote dashboard/_loader.py seja encontrado em qualquer CWD
sys.path.insert(0, str(Path(__file__).parent))

from _loader import load_data

st.set_page_config(
    page_title="CarMarket Analytics",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── cabeçalho ────────────────────────────────────────────────────────────────
st.title("CarMarket Analytics")
st.caption("Plataforma de análise de mercado de veículos usados — Mobato Analytics")

# ── resumo do dataset ─────────────────────────────────────────────────────────
df = load_data()

if df is not None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de anúncios", f"{len(df):,}")
    c2.metric("Preço médio", f"${df['price'].mean():,.0f}")
    c3.metric(
        "Fabricantes",
        f"{df['manufacturer'].nunique()}",
    )
    c4.metric(
        "Período",
        f"{int(df['year'].min())}–{int(df['year'].max())}",
    )

st.divider()

# ── navegação ─────────────────────────────────────────────────────────────────
st.subheader("Escolha sua área")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("### Comprador")
    st.markdown(
        "Encontre o carro ideal. "
        "Filtre por fabricante, ano, quilometragem e preço."
    )

with col2:
    st.markdown("### Vendedor")
    st.markdown(
        "Avalie o preço do seu carro com base no mercado atual "
        "e receba sugestões personalizadas."
    )

with col3:
    st.markdown("### Gestor")
    st.markdown(
        "Visão executiva do mercado: volume, valor total, "
        "tendências e segmentação de inventário."
    )

with col4:
    st.markdown("### Análise Avançada")
    st.markdown(
        "Modelos preditivos, segmentação por cluster, "
        "previsão temporal e análise regional."
    )

st.divider()
st.caption("Desenvolvido por Mobato Analytics · © 2026")

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Suporte")
    st.markdown("suporte@mobato.com  \n(11) 1234-5678")

    if df is not None:
        st.divider()
        st.markdown("**Fonte de dados**")
        st.caption("data/processed/cars_abt.csv")

import streamlit as st

st.set_page_config(
    page_title="Dashboard de Análise de Veículos",
    page_icon="🚗",
    layout="wide"
)

st.title("🚗 Dashboard de Análise de Veículos")
st.subheader("Bem-vindo ao Sistema de Análise de Mercado de Carros Usados")

st.markdown("""
### Escolha sua área:

1. **Área do Comprador** 🛒
   - Encontre o carro ideal para você
   - Compare preços e características
   - Visualize estatísticas do mercado
   - Filtre por suas preferências

2. **Área do Vendedor** 💰
   - Avalie o preço do seu carro
   - Veja análises de mercado
   - Compare com veículos similares
   - Receba sugestões de preço

3. **Área do Gestor** 📊
   - Analise tendências de mercado
   - Monitore métricas de desempenho
   - Visualize segmentação de mercado
   - Acompanhe indicadores chave
""")

st.markdown("""
### Como usar:

1. Selecione sua área no menu lateral
2. Use os filtros disponíveis para personalizar sua análise
3. Explore os gráficos e métricas interativos
4. Tome decisões baseadas em dados

### Recursos disponíveis:

- **Análise de Preços**: Compare preços por fabricante, modelo, ano e região
- **Análise de Mercado**: Visualize tendências, volumes e distribuições
- **Previsões**: Use modelos de machine learning para prever preços
- **Recomendações**: Receba sugestões personalizadas
""")

# Adicionar informações de contato ou suporte
st.sidebar.markdown("""
### Suporte

Em caso de dúvidas ou problemas, entre em contato:
- Email: suporte@mobato.com
- Tel: (11) 1234-5678
""")

# Adicionar footer
st.markdown("""
---
Desenvolvido por Mobato Analytics | © 2024
""") 
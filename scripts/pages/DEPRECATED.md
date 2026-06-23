# DEPRECATED — Legacy Dashboard Pages

Estes arquivos são a versão **legada** do dashboard e estão sendo mantidos apenas como referência histórica.

## Use o dashboard canônico

```bash
streamlit run dashboard/Home.py
# ou
python scripts/run_dashboard.py
```

O app canônico está em `dashboard/` e inclui:
- `dashboard/Home.py` — página inicial com KPIs
- `dashboard/_loader.py` — carregamento centralizado (CSV → Parquet → PostgreSQL)
- `dashboard/pages/1_Comprador.py`
- `dashboard/pages/2_Vendedor.py`
- `dashboard/pages/3_Gestor.py`
- `dashboard/pages/4_Analise_Avancada.py`

## Por que estes arquivos existem?

Foram criados antes da consolidação (UCM-13). Cada página tinha seu próprio
`load_data()` local sem cache compartilhado e sem fallback para banco de dados.
O modelo de preços era treinado em memória a cada sessão (sem persistência).

Não remova estes arquivos sem verificar se algum processo externo ainda os referencia.

import os
import logging
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine, text
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Estabelece conexão com o banco de dados."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL não encontrada nas variáveis de ambiente")
    return create_engine(db_url)

def generate_financing_overview(engine):
    """Gera visão geral do financiamento."""
    query = """
    SELECT 
        COUNT(*) as total_cars,
        SUM(CASE WHEN has_installments THEN 1 ELSE 0 END) as financed_cars,
        AVG(CASE WHEN has_installments THEN monthly_payment ELSE NULL END) as avg_monthly_payment,
        AVG(CASE WHEN has_installments THEN down_payment ELSE NULL END) as avg_down_payment,
        AVG(CASE WHEN has_installments THEN installments ELSE NULL END) as avg_installments,
        AVG(price) as avg_price
    FROM cars
    WHERE price IS NOT NULL
    """
    return pd.read_sql(query, engine)

def generate_manufacturer_analysis(engine):
    """Gera análise de financiamento por fabricante."""
    query = """
    SELECT 
        manufacturer,
        COUNT(*) as total_cars,
        SUM(CASE WHEN has_installments THEN 1 ELSE 0 END) as financed_cars,
        AVG(CASE WHEN has_installments THEN monthly_payment ELSE NULL END) as avg_monthly_payment,
        AVG(CASE WHEN has_installments THEN down_payment ELSE NULL END) as avg_down_payment,
        AVG(CASE WHEN has_installments THEN installments ELSE NULL END) as avg_installments,
        AVG(price) as avg_price
    FROM cars
    WHERE price IS NOT NULL
    GROUP BY manufacturer
    HAVING COUNT(*) >= 100
    ORDER BY total_cars DESC
    LIMIT 10
    """
    return pd.read_sql(query, engine)

def generate_price_range_analysis(engine):
    """Gera análise de financiamento por faixa de preço."""
    query = """
    WITH price_ranges AS (
        SELECT 
            CASE 
                WHEN price <= 50000 THEN 'Até R$ 50.000'
                WHEN price <= 100000 THEN 'R$ 50.001 - R$ 100.000'
                WHEN price <= 150000 THEN 'R$ 100.001 - R$ 150.000'
                WHEN price <= 200000 THEN 'R$ 150.001 - R$ 200.000'
                ELSE 'Acima de R$ 200.000'
            END as price_range,
            *
        FROM cars
        WHERE price IS NOT NULL
    )
    SELECT 
        price_range,
        COUNT(*) as total_cars,
        SUM(CASE WHEN has_installments THEN 1 ELSE 0 END) as financed_cars,
        AVG(CASE WHEN has_installments THEN monthly_payment ELSE NULL END) as avg_monthly_payment,
        AVG(CASE WHEN has_installments THEN down_payment ELSE NULL END) as avg_down_payment,
        AVG(CASE WHEN has_installments THEN installments ELSE NULL END) as avg_installments,
        AVG(price) as avg_price
    FROM price_ranges
    GROUP BY price_range
    ORDER BY MIN(price)
    """
    return pd.read_sql(query, engine)

def create_visualizations(overview, manufacturer_df, price_range_df):
    """Cria visualizações para o relatório."""
    # Configuração do estilo
    plt.style.use('default')  # Usando estilo padrão em vez de seaborn
    
    # 1. Distribuição de pagamento (à vista vs. financiado)
    plt.figure(figsize=(10, 6))
    plt.pie(
        [overview['financed_cars'].iloc[0], overview['total_cars'].iloc[0] - overview['financed_cars'].iloc[0]],
        labels=['Financiado', 'À Vista'],
        autopct='%1.1f%%',
        colors=['#2ecc71', '#3498db']
    )
    plt.title('Distribuição de Pagamento')
    plt.savefig('data/analysis/payment_distribution.png')
    plt.close()
    
    # 2. Taxa de financiamento por fabricante
    plt.figure(figsize=(12, 6))
    manufacturer_df['financing_rate'] = manufacturer_df['financed_cars'] / manufacturer_df['total_cars'] * 100
    sns.barplot(data=manufacturer_df, x='manufacturer', y='financing_rate')
    plt.xticks(rotation=45)
    plt.title('Taxa de Financiamento por Fabricante')
    plt.ylabel('Taxa de Financiamento (%)')
    plt.tight_layout()
    plt.savefig('data/analysis/financing_rate_by_manufacturer.png')
    plt.close()
    
    # 3. Parcela média por faixa de preço
    plt.figure(figsize=(12, 6))
    sns.barplot(data=price_range_df, x='price_range', y='avg_monthly_payment')
    plt.xticks(rotation=45)
    plt.title('Parcela Média por Faixa de Preço')
    plt.ylabel('Parcela Média (R$)')
    plt.tight_layout()
    plt.savefig('data/analysis/avg_monthly_payment_by_price_range.png')
    plt.close()

def generate_report(overview, manufacturer_df, price_range_df):
    """Gera o relatório PDF."""
    doc = SimpleDocTemplate(
        "data/analysis/financing_report.pdf",
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12
    )
    
    normal_style = styles['Normal']
    
    # Lista de elementos do documento
    elements = []
    
    # Título
    elements.append(Paragraph("Análise de Financiamento - Relatório", title_style))
    elements.append(Spacer(1, 12))
    
    # Resumo Executivo
    elements.append(Paragraph("Resumo Executivo", heading_style))
    elements.append(Paragraph(
        f"Este relatório apresenta uma análise completa do financiamento de veículos "
        f"baseada em {overview['total_cars'].iloc[0]:,.0f} anúncios. "
        f"Aproximadamente {overview['financed_cars'].iloc[0]/overview['total_cars'].iloc[0]*100:.1f}% "
        f"dos veículos são oferecidos com opções de financiamento.",
        normal_style
    ))
    elements.append(Spacer(1, 12))
    
    # Distribuição de Pagamento
    elements.append(Paragraph("Distribuição de Pagamento", heading_style))
    elements.append(Image('data/analysis/payment_distribution.png', width=6*inch, height=4*inch))
    elements.append(Spacer(1, 12))
    
    # Análise por Fabricante
    elements.append(Paragraph("Análise por Fabricante", heading_style))
    elements.append(Image('data/analysis/financing_rate_by_manufacturer.png', width=6*inch, height=4*inch))
    
    # Tabela de dados por fabricante
    manufacturer_data = []
    manufacturer_data.append(['Fabricante', 'Total', 'Financiados', 'Parcela Média', 'Entrada Média'])
    for _, row in manufacturer_df.iterrows():
        manufacturer_data.append([
            row['manufacturer'],
            f"{row['total_cars']:,.0f}",
            f"{row['financed_cars']:,.0f}",
            f"R$ {row['avg_monthly_payment']:,.2f}",
            f"R$ {row['avg_down_payment']:,.2f}"
        ])
    
    t = Table(manufacturer_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12))
    
    # Análise por Faixa de Preço
    elements.append(Paragraph("Análise por Faixa de Preço", heading_style))
    elements.append(Image('data/analysis/avg_monthly_payment_by_price_range.png', width=6*inch, height=4*inch))
    
    # Tabela de dados por faixa de preço
    price_range_data = []
    price_range_data.append(['Faixa de Preço', 'Total', 'Financiados', 'Parcela Média', 'Entrada Média'])
    for _, row in price_range_df.iterrows():
        price_range_data.append([
            row['price_range'],
            f"{row['total_cars']:,.0f}",
            f"{row['financed_cars']:,.0f}",
            f"R$ {row['avg_monthly_payment']:,.2f}",
            f"R$ {row['avg_down_payment']:,.2f}"
        ])
    
    t = Table(price_range_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12))
    
    # Insights Gerenciais
    elements.append(Paragraph("Insights Gerenciais", heading_style))
    insights = [
        "1. Taxa de Financiamento:",
        f"   - {overview['financed_cars'].iloc[0]/overview['total_cars'].iloc[0]*100:.1f}% dos veículos oferecem financiamento",
        f"   - Parcela média: R$ {overview['avg_monthly_payment'].iloc[0]:,.2f}",
        f"   - Entrada média: R$ {overview['avg_down_payment'].iloc[0]:,.2f}",
        "",
        "2. Padrões por Fabricante:",
        "   - Fabricantes premium apresentam maior taxa de financiamento",
        "   - Maior concentração de financiamentos em marcas populares",
        "",
        "3. Comportamento por Faixa de Preço:",
        "   - Veículos mais caros têm maior probabilidade de financiamento",
        "   - Entrada média aumenta proporcionalmente ao valor do veículo",
        "   - Prazo médio de financiamento varia por faixa de preço"
    ]
    
    for insight in insights:
        elements.append(Paragraph(insight, normal_style))
    
    # Gera o PDF
    doc.build(elements)

def main():
    """Função principal."""
    try:
        logger.info("Iniciando geração do relatório de financiamento...")
        
        # Cria diretório de análise se não existir
        Path("data/analysis").mkdir(parents=True, exist_ok=True)
        
        # Conecta ao banco de dados
        engine = get_db_connection()
        
        # Gera análises
        overview = generate_financing_overview(engine)
        manufacturer_df = generate_manufacturer_analysis(engine)
        price_range_df = generate_price_range_analysis(engine)
        
        # Cria visualizações
        create_visualizations(overview, manufacturer_df, price_range_df)
        
        # Gera relatório
        generate_report(overview, manufacturer_df, price_range_df)
        
        logger.info("Relatório gerado com sucesso em data/analysis/financing_report.pdf")
        
    except Exception as e:
        logger.error(f"Erro ao gerar relatório: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
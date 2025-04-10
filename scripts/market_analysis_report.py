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

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Estabelece conexão com o banco de dados."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL não encontrada nas variáveis de ambiente")
    return create_engine(db_url)

def get_manufacturer_prices(engine):
    """Obtém preço médio por fabricante."""
    query = """
    WITH price_limits AS (
        SELECT 
            manufacturer,
            CASE 
                WHEN LOWER(manufacturer) = 'ferrari' THEN 2000000
                WHEN LOWER(manufacturer) = 'lamborghini' THEN 2000000
                WHEN LOWER(manufacturer) = 'rolls-royce' THEN 2000000
                WHEN LOWER(manufacturer) = 'bentley' THEN 1000000
                WHEN LOWER(manufacturer) = 'porsche' THEN 1000000
                WHEN LOWER(manufacturer) = 'maserati' THEN 800000
                WHEN LOWER(manufacturer) = 'aston martin' THEN 1000000
                WHEN LOWER(manufacturer) = 'mercedes-benz' THEN 500000
                WHEN LOWER(manufacturer) = 'bmw' THEN 500000
                WHEN LOWER(manufacturer) = 'audi' THEN 500000
                WHEN LOWER(manufacturer) = 'lexus' THEN 400000
                WHEN LOWER(manufacturer) = 'tesla' THEN 200000
                ELSE 200000
            END as max_price
        FROM cars
    )
    SELECT 
        c.manufacturer,
        COUNT(*) as total_vehicles,
        AVG(c.price) as avg_price,
        MIN(c.price) as min_price,
        MAX(c.price) as max_price
    FROM cars c
    JOIN price_limits pl ON c.manufacturer = pl.manufacturer
    WHERE c.price IS NOT NULL 
    AND c.price <= pl.max_price
    GROUP BY c.manufacturer
    HAVING COUNT(*) >= 10
    ORDER BY avg_price DESC
    """
    return pd.read_sql(query, engine)

def get_top_models(engine):
    """Obtém os 5 modelos mais anunciados."""
    query = """
    SELECT 
        model,
        COUNT(*) as total_listings,
        AVG(odometer) as avg_mileage,
        AVG(price) as avg_price
    FROM cars
    WHERE model IS NOT NULL
    GROUP BY model
    ORDER BY total_listings DESC
    LIMIT 5
    """
    return pd.read_sql(query, engine)

def get_fuel_analysis(engine):
    """Obtém análise dos 3 tipos de combustível mais comuns."""
    query = """
    SELECT 
        fuel,
        COUNT(*) as total_vehicles,
        AVG(odometer) as avg_mileage,
        AVG(price) as avg_price
    FROM cars
    WHERE fuel IS NOT NULL
    GROUP BY fuel
    ORDER BY total_vehicles DESC
    LIMIT 3
    """
    return pd.read_sql(query, engine)

def get_top_regions(engine):
    """Obtém as 5 regiões com maiores preços médios."""
    query = """
    SELECT 
        state,
        COUNT(*) as total_vehicles,
        AVG(price) as avg_price,
        MIN(price) as min_price,
        MAX(price) as max_price
    FROM cars
    WHERE price IS NOT NULL AND state IS NOT NULL
    GROUP BY state
    HAVING COUNT(*) >= 10
    ORDER BY avg_price DESC
    LIMIT 5
    """
    return pd.read_sql(query, engine)

def get_transmission_distribution(engine):
    """Obtém distribuição de transmissão manual vs automática."""
    query = """
    WITH transmission_counts AS (
        SELECT 
            transmission,
            COUNT(*) as total
        FROM cars
        WHERE transmission IS NOT NULL
        GROUP BY transmission
    )
    SELECT 
        transmission,
        total,
        ROUND(100.0 * total / SUM(total) OVER(), 2) as percentage
    FROM transmission_counts
    ORDER BY total DESC
    """
    return pd.read_sql(query, engine)

def create_visualizations(manufacturer_df, models_df, fuel_df, regions_df, transmission_df):
    """Cria visualizações para o relatório."""
    plt.style.use('default')
    
    # 1. Top 10 fabricantes por preço médio
    plt.figure(figsize=(12, 6))
    sns.barplot(data=manufacturer_df.head(10), x='manufacturer', y='avg_price')
    plt.xticks(rotation=45)
    plt.title('Top 10 Fabricantes por Preço Médio')
    plt.ylabel('Preço Médio (R$)')
    plt.tight_layout()
    plt.savefig('data/analysis/manufacturer_prices.png')
    plt.close()
    
    # 2. Top 5 modelos mais anunciados
    plt.figure(figsize=(12, 6))
    sns.barplot(data=models_df, x='model', y='total_listings')
    plt.xticks(rotation=45)
    plt.title('Top 5 Modelos Mais Anunciados')
    plt.ylabel('Quantidade de Anúncios')
    plt.tight_layout()
    plt.savefig('data/analysis/top_models.png')
    plt.close()
    
    # 3. Distribuição por tipo de combustível
    plt.figure(figsize=(10, 6))
    plt.pie(
        fuel_df['total_vehicles'],
        labels=fuel_df['fuel'],
        autopct='%1.1f%%'
    )
    plt.title('Distribuição por Tipo de Combustível')
    plt.savefig('data/analysis/fuel_distribution.png')
    plt.close()
    
    # 4. Preço médio por região
    plt.figure(figsize=(12, 6))
    sns.barplot(data=regions_df, x='state', y='avg_price')
    plt.xticks(rotation=45)
    plt.title('Preço Médio por Região')
    plt.ylabel('Preço Médio (R$)')
    plt.tight_layout()
    plt.savefig('data/analysis/region_prices.png')
    plt.close()
    
    # 5. Distribuição de transmissão
    plt.figure(figsize=(10, 6))
    plt.pie(
        transmission_df['total'],
        labels=transmission_df['transmission'],
        autopct='%1.1f%%'
    )
    plt.title('Distribuição por Tipo de Transmissão')
    plt.savefig('data/analysis/transmission_distribution.png')
    plt.close()

def format_currency(value):
    """Formata valor monetário."""
    return f"R$ {value:,.2f}"

def format_number(value):
    """Formata número com separador de milhares."""
    return f"{value:,.0f}"

def generate_report(manufacturer_df, models_df, fuel_df, regions_df, transmission_df):
    """Gera o relatório PDF."""
    doc = SimpleDocTemplate(
        "data/analysis/market_analysis_report.pdf",
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
    
    elements = []
    
    # Título
    elements.append(Paragraph("Análise de Mercado - Veículos Usados", title_style))
    elements.append(Spacer(1, 12))
    
    # 1. Análise por Fabricante
    elements.append(Paragraph("1. Análise de Preços por Fabricante", heading_style))
    elements.append(Paragraph(
        f"Analisamos os preços médios por fabricante, considerando apenas fabricantes com 10 ou mais veículos anunciados. "
        f"O fabricante {manufacturer_df.iloc[0]['manufacturer']} apresenta o maior preço médio de {format_currency(manufacturer_df.iloc[0]['avg_price'])}.",
        normal_style
    ))
    elements.append(Image('data/analysis/manufacturer_prices.png', width=6*inch, height=4*inch))
    elements.append(Spacer(1, 12))
    
    # 2. Modelos Mais Anunciados
    elements.append(Paragraph("2. Modelos Mais Anunciados", heading_style))
    elements.append(Paragraph(
        f"Os 5 modelos mais anunciados representam uma parte significativa do mercado. "
        f"O modelo {models_df.iloc[0]['model']} lidera com {format_number(models_df.iloc[0]['total_listings'])} anúncios.",
        normal_style
    ))
    elements.append(Image('data/analysis/top_models.png', width=6*inch, height=4*inch))
    
    # Tabela de modelos
    models_data = [['Modelo', 'Total Anúncios', 'Km Média', 'Preço Médio']]
    for _, row in models_df.iterrows():
        models_data.append([
            row['model'],
            format_number(row['total_listings']),
            format_number(row['avg_mileage']),
            format_currency(row['avg_price'])
        ])
    
    t = Table(models_data)
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
    
    # 3. Análise de Combustível
    elements.append(Paragraph("3. Análise por Tipo de Combustível", heading_style))
    elements.append(Paragraph(
        f"Analisamos os 3 tipos de combustível mais comuns. "
        f"{fuel_df.iloc[0]['fuel']} é o mais comum, representando {fuel_df.iloc[0]['total_vehicles']} veículos.",
        normal_style
    ))
    elements.append(Image('data/analysis/fuel_distribution.png', width=6*inch, height=4*inch))
    
    # Tabela de combustível
    fuel_data = [['Combustível', 'Total', 'Km Média', 'Preço Médio']]
    for _, row in fuel_df.iterrows():
        fuel_data.append([
            row['fuel'],
            format_number(row['total_vehicles']),
            format_number(row['avg_mileage']),
            format_currency(row['avg_price'])
        ])
    
    t = Table(fuel_data)
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
    
    # 4. Análise Regional
    elements.append(Paragraph("4. Análise Regional", heading_style))
    elements.append(Paragraph(
        f"As 5 regiões com os maiores preços médios foram analisadas. "
        f"{regions_df.iloc[0]['state']} lidera com preço médio de {format_currency(regions_df.iloc[0]['avg_price'])}.",
        normal_style
    ))
    elements.append(Image('data/analysis/region_prices.png', width=6*inch, height=4*inch))
    
    # Tabela de regiões
    region_data = [['Estado', 'Total', 'Preço Médio', 'Preço Mínimo', 'Preço Máximo']]
    for _, row in regions_df.iterrows():
        region_data.append([
            row['state'],
            format_number(row['total_vehicles']),
            format_currency(row['avg_price']),
            format_currency(row['min_price']),
            format_currency(row['max_price'])
        ])
    
    t = Table(region_data)
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
    
    # 5. Análise de Transmissão
    elements.append(Paragraph("5. Análise de Transmissão", heading_style))
    elements.append(Paragraph(
        f"Analisamos a distribuição entre transmissão manual e automática. "
        f"{transmission_df.iloc[0]['transmission']} representa {transmission_df.iloc[0]['percentage']}% dos veículos.",
        normal_style
    ))
    elements.append(Image('data/analysis/transmission_distribution.png', width=6*inch, height=4*inch))
    
    # Tabela de transmissão
    transmission_data = [['Transmissão', 'Total', 'Porcentagem']]
    for _, row in transmission_df.iterrows():
        transmission_data.append([
            row['transmission'],
            format_number(row['total']),
            f"{row['percentage']:.1f}%"
        ])
    
    t = Table(transmission_data)
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
    
    # Gera o PDF
    doc.build(elements)

def main():
    """Função principal."""
    try:
        logger.info("Iniciando geração do relatório de análise de mercado...")
        
        # Cria diretório de análise se não existir
        Path("data/analysis").mkdir(parents=True, exist_ok=True)
        
        # Conecta ao banco de dados
        engine = get_db_connection()
        
        # Obtém os dados
        manufacturer_df = get_manufacturer_prices(engine)
        models_df = get_top_models(engine)
        fuel_df = get_fuel_analysis(engine)
        regions_df = get_top_regions(engine)
        transmission_df = get_transmission_distribution(engine)
        
        # Cria visualizações
        create_visualizations(manufacturer_df, models_df, fuel_df, regions_df, transmission_df)
        
        # Gera relatório
        generate_report(manufacturer_df, models_df, fuel_df, regions_df, transmission_df)
        
        logger.info("Relatório gerado com sucesso em data/analysis/market_analysis_report.pdf")
        
    except Exception as e:
        logger.error(f"Erro ao gerar relatório: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
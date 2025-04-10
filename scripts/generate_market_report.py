#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import matplotlib.pyplot as plt
import seaborn as sns

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_data():
    """Carrega os dados do arquivo CSV."""
    file_path = Path('data/processed/cars_abt.csv')
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    return pd.read_csv(file_path)

def load_sql_queries():
    """Carrega as queries SQL do arquivo."""
    sql_file = Path('sql/analysis/market_analysis.sql')
    if not sql_file.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {sql_file}")
    return sql_file.read_text()

def create_price_distribution_plot(df):
    """Cria gráfico de distribuição de preços."""
    plt.figure(figsize=(10, 6))
    sns.histplot(data=df, x='price', bins=50)
    plt.title('Distribuição dos Preços dos Veículos')
    plt.xlabel('Preço ($)')
    plt.ylabel('Frequência')
    plot_path = 'reports/figures/price_distribution.png'
    Path('reports/figures').mkdir(parents=True, exist_ok=True)
    plt.savefig(plot_path)
    plt.close()
    return plot_path

def create_year_price_plot(df):
    """Cria gráfico de relação ano vs preço."""
    year_price = df.groupby('year')['price'].mean().reset_index()
    plt.figure(figsize=(10, 6))
    sns.regplot(data=year_price, x='year', y='price')
    plt.title('Relação entre Ano e Preço Médio')
    plt.xlabel('Ano')
    plt.ylabel('Preço Médio ($)')
    plot_path = 'reports/figures/year_price_relation.png'
    plt.savefig(plot_path)
    plt.close()
    return plot_path

def create_mileage_fuel_plot(df):
    """Cria gráfico de quilometragem média por tipo de combustível."""
    plt.figure(figsize=(12, 6))
    mileage_by_fuel = df.groupby('fuel')['odometer'].mean().sort_values(ascending=False)
    sns.barplot(x=mileage_by_fuel.index, y=mileage_by_fuel.values)
    plt.title('Quilometragem Média por Tipo de Combustível')
    plt.xlabel('Tipo de Combustível')
    plt.ylabel('Quilometragem Média')
    plt.xticks(rotation=45)
    plot_path = 'reports/figures/mileage_by_fuel.png'
    plt.savefig(plot_path)
    plt.close()
    return plot_path

def create_mileage_manufacturer_plot(df):
    """Cria gráfico de quilometragem média por fabricante."""
    plt.figure(figsize=(12, 6))
    top_manufacturers = df.groupby('manufacturer')['odometer'].mean().sort_values(ascending=False).head(10)
    sns.barplot(x=top_manufacturers.index, y=top_manufacturers.values)
    plt.title('Quilometragem Média por Fabricante (Top 10)')
    plt.xlabel('Fabricante')
    plt.ylabel('Quilometragem Média')
    plt.xticks(rotation=45)
    plot_path = 'reports/figures/mileage_by_manufacturer.png'
    plt.savefig(plot_path)
    plt.close()
    return plot_path

def create_price_mileage_scatter(df):
    """Cria gráfico de dispersão preço vs quilometragem."""
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='odometer', y='price', alpha=0.5)
    plt.title('Relação entre Preço e Quilometragem')
    plt.xlabel('Quilometragem')
    plt.ylabel('Preço ($)')
    plot_path = 'reports/figures/price_mileage_scatter.png'
    plt.savefig(plot_path)
    plt.close()
    return plot_path

def create_outliers_boxplot(df):
    """Cria boxplot para visualização de outliers."""
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, y='price')
    plt.title('Boxplot de Preços - Identificação de Outliers')
    plt.ylabel('Preço ($)')
    plot_path = 'reports/figures/price_outliers.png'
    plt.savefig(plot_path)
    plt.close()
    return plot_path

def generate_report(df, sql_queries):
    """Gera o relatório PDF."""
    report_path = 'reports/market_analysis_report.pdf'
    Path('reports').mkdir(parents=True, exist_ok=True)
    
    # Configuração do documento
    doc = SimpleDocTemplate(
        report_path,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Conteúdo
    story = []
    
    # Título
    story.append(Paragraph("Análise Estatística do Mercado de Carros Usados", title_style))
    story.append(Spacer(1, 12))
    
    # Sumário Executivo
    story.append(Paragraph("Sumário Executivo", heading_style))
    story.append(Paragraph(f"""
    Este relatório apresenta uma análise estatística detalhada do mercado de carros usados baseada em {len(df):,} anúncios.
    A análise inclui distribuição de preços, relações entre variáveis e identificação de outliers.
    """, normal_style))
    story.append(Spacer(1, 12))
    
    # 1. Distribuição dos Preços
    story.append(Paragraph("1. Distribuição dos Preços dos Veículos", heading_style))
    price_stats = df['price'].describe()
    stats_data = [
        ['Estatística', 'Valor'],
        ['Média', f"${price_stats['mean']:,.2f}"],
        ['Mediana', f"${price_stats['50%']:,.2f}"],
        ['Desvio Padrão', f"${price_stats['std']:,.2f}"],
        ['Mínimo', f"${price_stats['min']:,.2f}"],
        ['Máximo', f"${price_stats['max']:,.2f}"],
        ['Q1 (25%)', f"${price_stats['25%']:,.2f}"],
        ['Q3 (75%)', f"${price_stats['75%']:,.2f}"]
    ]
    
    t = Table(stats_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 12))
    
    # Gráfico de distribuição de preços
    story.append(Paragraph("Distribuição dos Preços", styles['Heading3']))
    price_plot = create_price_distribution_plot(df)
    story.append(Image(price_plot, width=6*inch, height=4*inch))
    story.append(Spacer(1, 12))
    
    # 2. Relação Ano vs Preço
    story.append(Paragraph("2. Relação entre Ano de Fabricação e Preço", heading_style))
    year_price = df.groupby('year')['price'].mean().reset_index()
    story.append(Paragraph(f"""
    A análise mostra uma correlação positiva entre o ano de fabricação e o preço dos veículos.
    O coeficiente de correlação é de {year_price['year'].corr(year_price['price']):.3f}.
    """, normal_style))
    year_plot = create_year_price_plot(df)
    story.append(Image(year_plot, width=6*inch, height=4*inch))
    story.append(Spacer(1, 12))
    
    # 3. Quilometragem por Tipo de Combustível e Fabricante
    story.append(Paragraph("3. Variação da Quilometragem Média", heading_style))
    story.append(Paragraph("Por Tipo de Combustível:", styles['Heading3']))
    mileage_fuel_plot = create_mileage_fuel_plot(df)
    story.append(Image(mileage_fuel_plot, width=6*inch, height=4*inch))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Por Fabricante (Top 10):", styles['Heading3']))
    mileage_manufacturer_plot = create_mileage_manufacturer_plot(df)
    story.append(Image(mileage_manufacturer_plot, width=6*inch, height=4*inch))
    story.append(Spacer(1, 12))
    
    # 4. Correlação Quilometragem vs Preço
    story.append(Paragraph("4. Correlação entre Quilometragem e Preço", heading_style))
    correlation = df['odometer'].corr(df['price'])
    story.append(Paragraph(f"""
    A análise mostra uma correlação negativa entre quilometragem e preço.
    O coeficiente de correlação é de {correlation:.3f}, indicando que veículos com maior quilometragem
    tendem a ter preços menores.
    """, normal_style))
    price_mileage_plot = create_price_mileage_scatter(df)
    story.append(Image(price_mileage_plot, width=6*inch, height=4*inch))
    story.append(Spacer(1, 12))
    
    # 5. Análise de Outliers
    story.append(Paragraph("5. Identificação de Outliers", heading_style))
    Q1 = df['price'].quantile(0.25)
    Q3 = df['price'].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    outliers = df[(df['price'] < lower_bound) | (df['price'] > upper_bound)]
    
    story.append(Paragraph(f"""
    Utilizando o método do intervalo interquartil (IQR), foram identificados {len(outliers):,} outliers
    ({(len(outliers)/len(df)*100):.1f}% dos dados).
    
    Limites:
    - Limite Inferior: ${lower_bound:,.2f}
    - Limite Superior: ${upper_bound:,.2f}
    
    Exemplos de outliers (5 maiores preços):
    """, normal_style))
    
    top_outliers = outliers.nlargest(5, 'price')[['manufacturer', 'model', 'year', 'price']]
    outliers_data = [['Fabricante', 'Modelo', 'Ano', 'Preço']]
    for _, row in top_outliers.iterrows():
        outliers_data.append([
            row['manufacturer'],
            row['model'],
            str(row['year']),
            f"${row['price']:,.2f}"
        ])
    
    t = Table(outliers_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 12))
    
    outliers_plot = create_outliers_boxplot(df)
    story.append(Image(outliers_plot, width=6*inch, height=4*inch))
    story.append(Spacer(1, 12))
    
    # Scripts SQL
    story.append(Paragraph("Scripts SQL Utilizados", heading_style))
    story.append(Paragraph(sql_queries, normal_style))
    
    # Gera o PDF
    doc.build(story)
    logger.info(f"Relatório gerado em: {report_path}")

def main():
    """Função principal."""
    try:
        # Carrega dados
        logger.info("Carregando dados...")
        df = load_data()
        
        # Carrega queries SQL
        logger.info("Carregando queries SQL...")
        sql_queries = load_sql_queries()
        
        # Gera relatório
        logger.info("Gerando relatório PDF...")
        generate_report(df, sql_queries)
        
        logger.info("Processo concluído com sucesso!")
        
    except Exception as e:
        logger.error(f"Erro durante a geração do relatório: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para atualizar os dados existentes com informações de parcelamento.
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Adicionar o diretório raiz ao path para importar módulos
sys.path.append(str(Path(__file__).parent.parent))

from src.etl.transform import calculate_total_price

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Estabelece conexão com o banco de dados."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL não encontrada nas variáveis de ambiente")
    return create_engine(db_url)

def validate_installment_data(df):
    """Valida e corrige dados de financiamento."""
    # Converte valores para numérico
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df['monthly_payment'] = pd.to_numeric(df['monthly_payment'], errors='coerce')
    df['down_payment'] = pd.to_numeric(df['down_payment'], errors='coerce')
    df['installments'] = pd.to_numeric(df['installments'], errors='coerce')
    
    # Regras de validação
    df['has_installments'] = (
        df['monthly_payment'].notna() & 
        (df['monthly_payment'] > 0) & 
        (df['monthly_payment'] < df['price'])
    )
    
    # Corrige valores inválidos
    mask = df['has_installments']
    df.loc[~mask, ['monthly_payment', 'down_payment', 'installments']] = np.nan
    
    # Validação de entrada mínima (20% do valor)
    df.loc[mask & (df['down_payment'].isna()), 'down_payment'] = df['price'] * 0.2
    
    # Validação de número de parcelas (entre 12 e 60)
    df.loc[mask & (df['installments'].isna()), 'installments'] = 48
    df.loc[mask & (df['installments'] < 12), 'installments'] = 12
    df.loc[mask & (df['installments'] > 60), 'installments'] = 60
    
    # Validação final do valor da parcela
    df['total_financed'] = df['price'] - df['down_payment']
    df['max_payment'] = df['total_financed'] / 12  # Parcela máxima (financiamento em 12x)
    
    # Corrige parcelas que excedem o valor máximo possível
    invalid_payments = mask & (df['monthly_payment'] > df['max_payment'])
    df.loc[invalid_payments, 'monthly_payment'] = df.loc[invalid_payments, 'total_financed'] / df.loc[invalid_payments, 'installments']
    
    # Remove colunas temporárias
    df = df.drop(['total_financed', 'max_payment'], axis=1)
    
    return df

def update_database(engine, df):
    """Atualiza o banco de dados com os dados corrigidos."""
    try:
        # Atualiza em lotes de 1000 registros
        batch_size = 1000
        total_rows = len(df)
        
        for i in range(0, total_rows, batch_size):
            batch = df.iloc[i:i+batch_size]
            
            # Prepara query de atualização
            update_query = """
            UPDATE cars 
            SET 
                has_installments = :has_installments,
                monthly_payment = CASE 
                    WHEN :has_installments = FALSE THEN 0 
                    ELSE COALESCE(:monthly_payment, 0) 
                END,
                down_payment = CASE 
                    WHEN :has_installments = FALSE THEN 0 
                    ELSE COALESCE(:down_payment, 0) 
                END,
                installments = CASE 
                    WHEN :has_installments = FALSE THEN 0 
                    ELSE COALESCE(:installments, 48) 
                END
            WHERE original_id = :original_id
            """
            
            # Executa atualização
            with engine.begin() as conn:
                for _, row in batch.iterrows():
                    # Converte NaN para None para o SQL
                    monthly_payment = float(row['monthly_payment']) if pd.notna(row['monthly_payment']) else None
                    down_payment = float(row['down_payment']) if pd.notna(row['down_payment']) else None
                    installments = int(row['installments']) if pd.notna(row['installments']) else None
                    
                    conn.execute(text(update_query), {
                        'original_id': int(row['original_id']),
                        'has_installments': bool(row['has_installments']),
                        'monthly_payment': monthly_payment,
                        'down_payment': down_payment,
                        'installments': installments
                    })
            
            logger.info(f"Atualizados {i + len(batch)} de {total_rows} registros")
            
    except Exception as e:
        logger.error(f"Erro ao atualizar banco de dados: {str(e)}")
        raise

def update_statistics(engine):
    """Atualiza as tabelas de estatísticas com informações de parcelamento."""
    logger.info("Atualizando estatísticas...")
    
    # Atualizar estatísticas por fabricante
    with engine.connect() as connection:
        connection.execute(text("""
        UPDATE manufacturer_stats
        SET 
            total_installment_cars = (
                SELECT COUNT(*) 
                FROM cars c 
                WHERE c.manufacturer = manufacturer_stats.manufacturer 
                AND c.has_installments = TRUE
            ),
            avg_monthly_payment = (
                SELECT AVG(monthly_payment) 
                FROM cars c 
                WHERE c.manufacturer = manufacturer_stats.manufacturer 
                AND c.has_installments = TRUE
            ),
            avg_down_payment = (
                SELECT AVG(down_payment) 
                FROM cars c 
                WHERE c.manufacturer = manufacturer_stats.manufacturer 
                AND c.has_installments = TRUE
            ),
            avg_installments = (
                SELECT AVG(installments) 
                FROM cars c 
                WHERE c.manufacturer = manufacturer_stats.manufacturer 
                AND c.has_installments = TRUE
            ),
            last_updated = CURRENT_TIMESTAMP
        """))
        connection.commit()
    
    # Atualizar estatísticas por estado
    with engine.connect() as connection:
        connection.execute(text("""
        UPDATE state_stats
        SET 
            total_installment_cars = (
                SELECT COUNT(*) 
                FROM cars c 
                WHERE c.state = state_stats.state 
                AND c.has_installments = TRUE
            ),
            avg_monthly_payment = (
                SELECT AVG(monthly_payment) 
                FROM cars c 
                WHERE c.state = state_stats.state 
                AND c.has_installments = TRUE
            ),
            avg_down_payment = (
                SELECT AVG(down_payment) 
                FROM cars c 
                WHERE c.state = state_stats.state 
                AND c.has_installments = TRUE
            ),
            avg_installments = (
                SELECT AVG(installments) 
                FROM cars c 
                WHERE c.state = state_stats.state 
                AND c.has_installments = TRUE
            ),
            last_updated = CURRENT_TIMESTAMP
        """))
        connection.commit()
    
    # Atualizar estatísticas por ano
    with engine.connect() as connection:
        connection.execute(text("""
        UPDATE year_stats
        SET 
            total_installment_cars = (
                SELECT COUNT(*) 
                FROM cars c 
                WHERE c.year = year_stats.year 
                AND c.has_installments = TRUE
            ),
            avg_monthly_payment = (
                SELECT AVG(monthly_payment) 
                FROM cars c 
                WHERE c.year = year_stats.year 
                AND c.has_installments = TRUE
            ),
            avg_down_payment = (
                SELECT AVG(down_payment) 
                FROM cars c 
                WHERE c.year = year_stats.year 
                AND c.has_installments = TRUE
            ),
            avg_installments = (
                SELECT AVG(installments) 
                FROM cars c 
                WHERE c.year = year_stats.year 
                AND c.has_installments = TRUE
            ),
            last_updated = CURRENT_TIMESTAMP
        """))
        connection.commit()
    
    # Inserir ou atualizar estatísticas de parcelamento
    with engine.connect() as connection:
        connection.execute(text("""
        INSERT INTO installment_stats (
            manufacturer, model, year, total_cars, total_installment_cars,
            avg_monthly_payment, avg_down_payment, avg_installments,
            avg_total_price, avg_original_price, price_difference_percent
        )
        SELECT 
            manufacturer, model, year, COUNT(*) as total_cars,
            SUM(CASE WHEN has_installments THEN 1 ELSE 0 END) as total_installment_cars,
            AVG(CASE WHEN has_installments THEN monthly_payment ELSE NULL END) as avg_monthly_payment,
            AVG(CASE WHEN has_installments THEN down_payment ELSE NULL END) as avg_down_payment,
            AVG(CASE WHEN has_installments THEN installments ELSE NULL END) as avg_installments,
            AVG(price) as avg_total_price,
            AVG(price_original) as avg_original_price,
            CASE 
                WHEN AVG(price_original) > 0 THEN 
                    ((AVG(price) - AVG(price_original)) / AVG(price_original)) * 100
                ELSE 0
            END as price_difference_percent
        FROM cars
        GROUP BY manufacturer, model, year
        ON CONFLICT (manufacturer, model, year) DO UPDATE
        SET 
            total_cars = EXCLUDED.total_cars,
            total_installment_cars = EXCLUDED.total_installment_cars,
            avg_monthly_payment = EXCLUDED.avg_monthly_payment,
            avg_down_payment = EXCLUDED.avg_down_payment,
            avg_installments = EXCLUDED.avg_installments,
            avg_total_price = EXCLUDED.avg_total_price,
            avg_original_price = EXCLUDED.avg_original_price,
            price_difference_percent = EXCLUDED.price_difference_percent,
            last_updated = CURRENT_TIMESTAMP
        """))
        connection.commit()
    
    logger.info("Estatísticas atualizadas")

def main():
    """Função principal."""
    try:
        logger.info("Iniciando atualização dos dados de financiamento...")
        
        # Conecta ao banco de dados
        engine = get_db_connection()
        
        # Carrega dados
        query = """
        SELECT 
            original_id, price, monthly_payment, down_payment, 
            installments, has_installments
        FROM cars
        """
        df = pd.read_sql(query, engine)
        
        # Valida e corrige dados
        logger.info(f"Validando {len(df)} registros...")
        df = validate_installment_data(df)
        
        # Atualiza banco de dados
        logger.info("Atualizando banco de dados...")
        update_database(engine, df)
        
        # Atualiza estatísticas
        update_statistics(engine)
        
        logger.info("Atualização concluída com sucesso!")
        
    except Exception as e:
        logger.error(f"Erro durante a atualização: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
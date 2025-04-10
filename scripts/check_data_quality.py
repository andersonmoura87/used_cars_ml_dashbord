import os
import sys
import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

def get_db_connection():
    """Estabelece conexão com o banco de dados."""
    try:
        engine = create_engine(
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
            f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}",
            connect_args={'client_encoding': 'utf8'}
        )
        return engine
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        sys.exit(1)

def load_data(engine):
    """Carrega dados do banco para análise."""
    logger.info("Carregando dados para análise de qualidade...")
    
    query = """
    SELECT 
        original_id,
        manufacturer,
        model,
        year,
        price,
        price_original,
        has_installments,
        monthly_payment,
        down_payment,
        installments,
        condition,
        odometer,
        title_status,
        transmission,
        region
    FROM cars
    """
    
    try:
        # Usar encoding específico ao carregar os dados
        df = pd.read_sql(query, engine, coerce_float=True)
        
        # Limpar caracteres especiais
        text_columns = ['manufacturer', 'model', 'condition', 'title_status', 'transmission', 'region']
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).apply(lambda x: x.encode('ascii', 'ignore').decode('ascii'))
        
        logger.info(f"Carregados {len(df)} registros para análise")
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar dados: {str(e)}")
        sys.exit(1)

def check_numeric_values(df):
    """Verifica consistência dos valores numéricos."""
    logger.info("Verificando valores numéricos...")
    
    # Verificar limites dos campos numéricos
    numeric_fields = ['price', 'price_original', 'monthly_payment', 'down_payment']
    max_value = 99999999.99
    
    for field in numeric_fields:
        invalid_values = df[df[field] > max_value]
        if len(invalid_values) > 0:
            logger.warning(f"Encontrados {len(invalid_values)} registros com {field} acima do limite")
            logger.warning(f"IDs problemáticos: {invalid_values['original_id'].tolist()[:5]}")
        
        negative_values = df[df[field] < 0]
        if len(negative_values) > 0:
            logger.warning(f"Encontrados {len(negative_values)} registros com {field} negativo")
            logger.warning(f"IDs problemáticos: {negative_values['original_id'].tolist()[:5]}")

def check_installment_consistency(df):
    """Verifica consistência dos dados de parcelamento."""
    logger.info("Verificando consistência dos dados de parcelamento...")
    
    # Verificar registros com has_installments=True mas sem valores de parcelamento
    invalid_installments = df[
        (df['has_installments'] == True) & 
        ((df['monthly_payment'].isna()) | (df['monthly_payment'] == 0) | 
         (df['installments'].isna()) | (df['installments'] == 0))
    ]
    
    if len(invalid_installments) > 0:
        logger.warning(f"Encontrados {len(invalid_installments)} registros com has_installments=True mas sem dados de parcelamento")
        logger.warning(f"IDs problemáticos: {invalid_installments['original_id'].tolist()[:5]}")
    
    # Verificar consistência entre preço total e valores de parcelamento
    df['calculated_total'] = df.apply(
        lambda row: (row['monthly_payment'] * row['installments'] + row['down_payment']) 
        if row['has_installments'] else row['price'],
        axis=1
    )
    
    inconsistent_prices = df[
        (df['has_installments'] == True) & 
        (abs(df['price'] - df['calculated_total']) > 0.01)
    ]
    
    if len(inconsistent_prices) > 0:
        logger.warning(f"Encontrados {len(inconsistent_prices)} registros com inconsistência entre preço total e valores de parcelamento")
        logger.warning(f"IDs problemáticos: {inconsistent_prices['original_id'].tolist()[:5]}")

def check_missing_values(df):
    """Verifica valores ausentes ou inválidos."""
    logger.info("Verificando valores ausentes ou inválidos...")
    
    # Verificar campos obrigatórios
    required_fields = ['manufacturer', 'model', 'year', 'price']
    for field in required_fields:
        missing_values = df[df[field].isna()]
        if len(missing_values) > 0:
            logger.warning(f"Encontrados {len(missing_values)} registros com {field} ausente")
            logger.warning(f"IDs problemáticos: {missing_values['original_id'].tolist()[:5]}")
    
    # Verificar valores inválidos em campos específicos
    invalid_years = df[(df['year'] < 1900) | (df['year'] > 2024)]
    if len(invalid_years) > 0:
        logger.warning(f"Encontrados {len(invalid_years)} registros com ano inválido")
        logger.warning(f"IDs problemáticos: {invalid_years['original_id'].tolist()[:5]}")

def check_price_anomalies(df):
    """Verifica anomalias nos preços."""
    logger.info("Verificando anomalias nos preços...")
    
    # Calcular estatísticas por fabricante
    manufacturer_stats = df.groupby('manufacturer').agg({
        'price': ['mean', 'std', 'min', 'max', 'count']
    })
    
    # Identificar preços muito baixos ou muito altos por fabricante
    for manufacturer in df['manufacturer'].unique():
        if manufacturer in manufacturer_stats.index:
            stats = manufacturer_stats.loc[manufacturer]
            mean_price = stats[('price', 'mean')]
            std_price = stats[('price', 'std')]
            
            # Preços muito baixos (menos de 10% da média)
            low_prices = df[
                (df['manufacturer'] == manufacturer) & 
                (df['price'] < mean_price * 0.1)
            ]
            
            if len(low_prices) > 0:
                logger.warning(f"Encontrados {len(low_prices)} registros com preço muito baixo para {manufacturer}")
                logger.warning(f"IDs problemáticos: {low_prices['original_id'].tolist()[:5]}")
            
            # Preços muito altos (mais de 3 desvios padrão da média)
            high_prices = df[
                (df['manufacturer'] == manufacturer) & 
                (df['price'] > mean_price + 3 * std_price)
            ]
            
            if len(high_prices) > 0:
                logger.warning(f"Encontrados {len(high_prices)} registros com preço muito alto para {manufacturer}")
                logger.warning(f"IDs problemáticos: {high_prices['original_id'].tolist()[:5]}")

def main():
    """Função principal."""
    try:
        # Conectar ao banco de dados
        engine = get_db_connection()
        
        # Carregar dados
        df = load_data(engine)
        
        # Executar verificações
        check_numeric_values(df)
        check_installment_consistency(df)
        check_missing_values(df)
        check_price_anomalies(df)
        
        logger.info("Análise de qualidade concluída")
        
    except Exception as e:
        logger.error(f"Erro durante a análise de qualidade: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
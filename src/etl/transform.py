import pandas as pd
import numpy as np
import logging
from datetime import datetime
import re
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_price_info(price_str, description):
    """Extrai informações de preço do texto, tratando casos de parcelas."""
    try:
        # Se o preço já é um número, retorna ele mesmo
        if isinstance(price_str, (int, float)):
            return float(price_str)
        
        # Procura por padrões de parcelas no texto
        monthly_pattern = r'(\$?\d+[.,]\d+|\d+)(?:\s*(?:x|×)\s*|\s+parcelas?\s+de\s+)(\d+[.,]\d+|\d+)'
        down_payment_pattern = r'entrada\s+(?:de\s+)?(\$?\d+[.,]\d+|\d+)'
        
        price = 0.0
        
        # Verifica se há informação de parcelas
        if description and isinstance(description, str):
            # Procura por parcelas
            monthly_match = re.search(monthly_pattern, description.lower())
            if monthly_match:
                num_payments = float(monthly_match.group(1).replace('$', '').replace(',', '.'))
                payment_value = float(monthly_match.group(2).replace(',', '.'))
                price = num_payments * payment_value
            
            # Procura por entrada
            down_payment_match = re.search(down_payment_pattern, description.lower())
            if down_payment_match:
                down_payment = float(down_payment_match.group(1).replace('$', '').replace(',', '.'))
                price += down_payment
        
        # Se não encontrou parcelas, tenta converter o preço direto
        if price == 0.0 and price_str:
            price = float(str(price_str).replace('$', '').replace(',', '').strip())
        
        return price
    except:
        return None

def clean_price_data(df):
    """Limpa e valida os preços dos carros."""
    try:
        # Criar cópia do DataFrame
        df_clean = df.copy()
        
        # Definir limites de preço por fabricante
        price_limits = {
            'toyota': (5000, 150000),
            'honda': (4000, 130000),
            'ford': (3000, 120000),
            'chevrolet': (3000, 110000),
            'bmw': (10000, 200000),
            'mercedes-benz': (12000, 250000),
            'audi': (10000, 180000),
            'volkswagen': (3000, 100000),
            'hyundai': (3000, 90000),
            'kia': (3000, 85000)
        }
        
        # Aplicar limites de preço por fabricante
        df_clean['price_valid'] = df_clean.apply(
            lambda row: (
                price_limits.get(str(row['manufacturer']).lower(), (2000, 300000))[0] <= row['price'] <= 
                price_limits.get(str(row['manufacturer']).lower(), (2000, 300000))[1]
                if pd.notnull(row['price']) else False
            ),
            axis=1
        )
        
        # Detectar anomalias usando Isolation Forest
        price_model = IsolationForest(contamination=0.1, random_state=42)
        
        # Preparar dados para detecção de anomalias
        price_features = df_clean[['price', 'year', 'odometer']].copy()
        price_features = price_features.fillna(price_features.mean())
        
        # Normalizar dados
        scaler = StandardScaler()
        price_features_scaled = scaler.fit_transform(price_features)
        
        # Detectar anomalias
        anomalies = price_model.fit_predict(price_features_scaled)
        df_clean['price_anomaly'] = anomalies
        
        # Remover preços inválidos e anômalos
        df_removed = df_clean[
            (~df_clean['price_valid']) | (df_clean['price_anomaly'] == -1)
        ].copy()
        
        df_clean = df_clean[
            df_clean['price_valid'] & (df_clean['price_anomaly'] == 1)
        ].copy()
        
        # Guardar preço original
        df_clean['price_original'] = df_clean['price']
        
        # Remover colunas temporárias
        df_clean = df_clean.drop(['price_valid', 'price_anomaly'], axis=1)
        
        # Log das remoções
        total_removed = len(df_removed)
        total_kept = len(df_clean)
        logger.info(f"Total de registros removidos por preço inválido/anômalo: {total_removed}")
        logger.info(f"Total de registros mantidos: {total_kept}")
        
        return df_clean, df_removed
    except Exception as e:
        logger.error(f"Erro ao limpar preços: {str(e)}")
        raise

def clean_text_data(df):
    """Limpa e padroniza dados de texto."""
    try:
        df_clean = df.copy()
        
        # Padronizar fabricantes
        df_clean['manufacturer'] = df_clean['manufacturer'].fillna('unknown').astype(str).str.lower().str.strip()
        
        # Padronizar modelos
        df_clean['model'] = df_clean['model'].fillna('unknown').astype(str).str.lower().str.strip()
        
        # Padronizar tipos de combustível
        fuel_mapping = {
            'gas': 'gasoline',
            'petrol': 'gasoline',
            'diesel fuel': 'diesel',
            'flex': 'hybrid',
            'electric fuel': 'electric'
        }
        df_clean['fuel'] = df_clean['fuel'].fillna('unknown').astype(str).str.lower().str.strip().map(lambda x: fuel_mapping.get(x, x))
        
        # Padronizar transmissão
        transmission_mapping = {
            'manual': 'manual',
            'automatic': 'automatic',
            'automated': 'automatic',
            'auto': 'automatic',
            'cvt': 'automatic'
        }
        df_clean['transmission'] = df_clean['transmission'].fillna('unknown').astype(str).str.lower().str.strip().map(lambda x: transmission_mapping.get(x, x))
        
        # Padronizar estados
        df_clean['state'] = df_clean['state'].fillna('unknown').astype(str).str.upper().str.strip()
        
        return df_clean
    except Exception as e:
        logger.error(f"Erro ao limpar dados de texto: {str(e)}")
        raise

def calculate_market_stats(df):
    """Calcula estatísticas de mercado."""
    try:
        # Usar datas UTC consistentemente
        df = df.copy()
        now = pd.Timestamp.now(tz='UTC')
        
        # Agrupar por fabricante, modelo e ano
        stats = df.groupby(['manufacturer', 'model', 'year']).agg({
            'price': ['mean', 'median', 'min', 'max', 'count'],
            'posting_date': lambda x: (now - x.max()).days
        }).reset_index()
        
        # Renomear colunas
        stats.columns = [
            'manufacturer', 'model', 'year', 'avg_price', 'median_price',
            'min_price', 'max_price', 'total_listings', 'days_listed'
        ]
        
        # Adicionar data do cálculo
        stats['calculated_at'] = now
        
        return stats
    except Exception as e:
        logger.error(f"Erro ao calcular estatísticas de mercado: {str(e)}")
        raise

def calculate_total_price(price_str: str, description: str, num_installments: int = 48) -> dict:
    """
    Calcula o valor total do veículo considerando parcelamento e entrada.
    
    Args:
        price_str: Valor do preço como string
        description: Descrição do anúncio
        num_installments: Número de parcelas padrão (default: 48)
        
    Returns:
        Dicionário com informações de preço:
        - has_installments: se tem informação de parcelas
        - monthly_payment: valor da parcela
        - down_payment: valor da entrada
        - total_price: preço total calculado
        - installments: número de parcelas
        - original_price: preço original
    """
    result = {
        'has_installments': False,
        'monthly_payment': None,
        'down_payment': None,
        'total_price': None,
        'installments': None,
        'original_price': None
    }
    
    try:
        # Converter preço original
        if isinstance(price_str, (int, float)):
            result['original_price'] = float(price_str)
        elif price_str:
            result['original_price'] = float(str(price_str).replace('$', '').replace(',', '').strip())
        
        if not description or not isinstance(description, str):
            return result
            
        # Procurar padrões de parcelas e entrada
        monthly_pattern = r'(\$?\d+[.,]\d+|\d+)(?:\s*(?:x|×)\s*|\s+parcelas?\s+de\s+)(\d+[.,]\d+|\d+)'
        down_payment_pattern = r'entrada\s+(?:de\s+)?(\$?\d+[.,]\d+|\d+)'
        installments_pattern = r'(\d+)\s*(?:x|parcelas|vezes)'
        
        # Extrair valor das parcelas
        monthly_match = re.search(monthly_pattern, description.lower())
        if monthly_match:
            result['has_installments'] = True
            # O grupo 2 é o valor da parcela
            result['monthly_payment'] = float(monthly_match.group(2).replace('$', '').replace(',', '.'))
            
            # Tentar extrair número de parcelas
            installments_match = re.search(installments_pattern, description.lower())
            if installments_match:
                result['installments'] = int(installments_match.group(1))
            else:
                result['installments'] = num_installments
        
        # Extrair valor da entrada
        down_payment_match = re.search(down_payment_pattern, description.lower())
        if down_payment_match:
            result['down_payment'] = float(down_payment_match.group(1).replace('$', '').replace(',', '.'))
            
        # Calcular preço total
        if result['has_installments']:
            total = 0
            if result['monthly_payment']:
                total += result['monthly_payment'] * result['installments']
            if result['down_payment']:
                total += result['down_payment']
            result['total_price'] = total
        else:
            result['total_price'] = result['original_price']
            
        return result
        
    except Exception as e:
        logger.error(f"Erro ao calcular preço total: {str(e)}")
        return result

def calculate_market_statistics(df: pd.DataFrame) -> dict:
    """
    Calcula estatísticas de mercado segmentadas por fabricante, estado e ano.

    Returns:
        dict com chaves 'manufacturer', 'state' e 'year', cada uma contendo
        um DataFrame de agregações prontas para carga no banco de dados.
    """
    try:
        agg_cfg = {
            'price': ['mean', 'min', 'max', 'count'],
        }

        manufacturer_stats = df.groupby('manufacturer').agg(agg_cfg).reset_index()
        manufacturer_stats.columns = ['manufacturer', 'avg_price', 'min_price', 'max_price', 'total_listings']
        if 'year' in df.columns:
            manufacturer_stats['avg_year'] = df.groupby('manufacturer')['year'].mean().values
        for col in ['has_installments', 'monthly_payment', 'down_payment', 'installments']:
            if col in df.columns:
                manufacturer_stats[f'avg_{col}' if col != 'has_installments' else 'total_financed'] = (
                    df.groupby('manufacturer')[col].sum().values
                    if col == 'has_installments'
                    else df.groupby('manufacturer')[col].mean().values
                )

        state_stats = df.groupby('state').agg(agg_cfg).reset_index()
        state_stats.columns = ['state', 'avg_price', 'min_price', 'max_price', 'total_listings']
        for col in ['has_installments', 'monthly_payment', 'down_payment', 'installments']:
            if col in df.columns:
                state_stats[f'avg_{col}' if col != 'has_installments' else 'total_financed'] = (
                    df.groupby('state')[col].sum().values
                    if col == 'has_installments'
                    else df.groupby('state')[col].mean().values
                )

        year_stats = df.groupby('year').agg(agg_cfg).reset_index()
        year_stats.columns = ['year', 'avg_price', 'min_price', 'max_price', 'total_listings']
        for col in ['has_installments', 'monthly_payment', 'down_payment', 'installments']:
            if col in df.columns:
                year_stats[f'avg_{col}' if col != 'has_installments' else 'total_financed'] = (
                    df.groupby('year')[col].sum().values
                    if col == 'has_installments'
                    else df.groupby('year')[col].mean().values
                )

        return {
            'manufacturer': manufacturer_stats,
            'state': state_stats,
            'year': year_stats,
        }
    except Exception as e:
        logger.error(f"Erro ao calcular estatísticas segmentadas: {str(e)}")
        raise


def transform_data(df: pd.DataFrame):
    """
    Função principal de transformação dos dados.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
            df_clean         — registros aprovados após limpeza
            df_removed       — registros descartados (preço inválido/anômalo)
            market_stats     — estatísticas de mercado (groupby manufacturer/model/year)
            transform_metadata — métricas da etapa para auditoria
    """
    logger.info("Iniciando transformação dos dados...")

    try:
        transform_start = datetime.now()
        df_input = df.copy()

        # --- Enriquecimento de preço (parcelas + entrada) ---
        logger.info("Calculando preços totais...")
        price_info = df_input.apply(
            lambda row: calculate_total_price(row['price'], row.get('description', '')),
            axis=1,
        )

        df_input['price_original'] = price_info.apply(lambda x: x['original_price'])
        df_input['has_installments'] = price_info.apply(lambda x: x['has_installments'])
        df_input['monthly_payment'] = price_info.apply(lambda x: x['monthly_payment'])
        df_input['down_payment'] = price_info.apply(lambda x: x['down_payment'])
        df_input['installments'] = price_info.apply(lambda x: x['installments'])
        df_input['price'] = price_info.apply(lambda x: x['total_price'])

        df_input['price'] = df_input['price'].fillna(df_input['price_original'])
        df_input = df_input[df_input['price'] > 0]

        # --- Limpeza avançada de preço (outliers + fabricante) ---
        df_clean, df_removed = clean_price_data(df_input)

        # --- Filtros adicionais ---
        current_year = datetime.now().year
        df_clean['vehicle_age'] = current_year - df_clean['year']

        df_clean = df_clean[
            (df_clean['year'] >= 1950) & (df_clean['year'] <= current_year + 1)
        ]

        # --- Padronização de texto ---
        text_columns = [
            'manufacturer', 'model', 'condition', 'fuel', 'title_status',
            'transmission', 'drive', 'size', 'type', 'paint_color',
        ]
        for col in text_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].fillna('unknown').str.lower().str.strip()

        # --- Estatísticas de mercado ---
        market_stats = calculate_market_stats(df_clean)

        transform_metadata = {
            'transform_start': transform_start.isoformat(),
            'transform_end': datetime.now().isoformat(),
            'input_records': len(df),
            'output_records': len(df_clean),
            'removed_records': len(df_removed),
        }

        logger.info(f"Transformação concluída. Registros finais: {len(df_clean)}")
        return df_clean, df_removed, market_stats, transform_metadata

    except Exception as e:
        logger.error(f"Erro na transformação dos dados: {str(e)}")
        raise 
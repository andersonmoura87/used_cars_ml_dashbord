import pandas as pd
import numpy as np
import re
from typing import Tuple, Dict
from sklearn.ensemble import IsolationForest

def extract_payment_info(description: str) -> Dict:
    """
    Extrai informações de pagamento da descrição do anúncio.
    
    Args:
        description: Texto da descrição do anúncio
        
    Returns:
        Dicionário com informações de pagamento
    """
    if pd.isna(description):
        return {
            'has_payment_info': False,
            'monthly_payment': None,
            'down_payment': None,
            'total_price': None
        }
    
    description = description.lower()
    
    # Padrões para encontrar valores monetários
    payment_patterns = {
        'monthly': r'\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:\/|\s+per\s+)?\s*(?:month|mo|mensal)',
        'down': r'(?:down\s+payment|entrada)\s*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        'total': r'(?:total\s+price|price|valor\s+total)\s*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
    }
    
    results = {
        'has_payment_info': False,
        'monthly_payment': None,
        'down_payment': None,
        'total_price': None
    }
    
    # Procurar por cada tipo de pagamento
    for payment_type, pattern in payment_patterns.items():
        match = re.search(pattern, description)
        if match:
            results['has_payment_info'] = True
            value = float(match.group(1).replace(',', ''))
            
            if payment_type == 'monthly':
                results['monthly_payment'] = value
            elif payment_type == 'down':
                results['down_payment'] = value
            else:  # total
                results['total_price'] = value
    
    return results

def estimate_total_price(payment_info: Dict) -> float:
    """
    Estima o preço total baseado nas informações de pagamento.
    
    Args:
        payment_info: Dicionário com informações de pagamento
        
    Returns:
        Preço total estimado ou None se não for possível estimar
    """
    if not payment_info['has_payment_info']:
        return None
        
    if payment_info['total_price']:
        return payment_info['total_price']
    
    # Se tiver pagamento mensal, assume financiamento de 48 meses
    if payment_info['monthly_payment']:
        monthly = payment_info['monthly_payment']
        down = payment_info['down_payment'] or 0
        return down + (monthly * 48)  # Estimativa conservadora
        
    return None

def get_manufacturer_price_limits() -> Dict:
    """
    Define limites de preço por fabricante baseado em conhecimento do mercado.
    """
    return {
        'ferrari': {'min': 100000, 'max': 2000000},
        'lamborghini': {'min': 100000, 'max': 2000000},
        'rolls-royce': {'min': 100000, 'max': 2000000},
        'bentley': {'min': 80000, 'max': 1000000},
        'porsche': {'min': 50000, 'max': 1000000},
        'maserati': {'min': 50000, 'max': 800000},
        'aston martin': {'min': 80000, 'max': 1000000},
        'mercedes-benz': {'min': 20000, 'max': 500000},
        'bmw': {'min': 20000, 'max': 500000},
        'audi': {'min': 20000, 'max': 500000},
        'lexus': {'min': 20000, 'max': 400000},
        'tesla': {'min': 30000, 'max': 200000},
        'default': {'min': 5000, 'max': 200000}
    }

def detect_price_anomalies(df: pd.DataFrame, contamination: float = 0.1) -> pd.Series:
    """
    Detecta anomalias nos preços usando Isolation Forest.
    
    Args:
        df: DataFrame com os dados
        contamination: Proporção esperada de outliers
        
    Returns:
        Series booleana indicando quais registros são anomalias
    """
    # Preparar features para detecção de anomalias
    features = ['price', 'year']
    if 'odometer' in df.columns:
        features.append('odometer')
    
    # Treinar modelo
    iso_forest = IsolationForest(contamination=contamination, random_state=42)
    anomalies = iso_forest.fit_predict(df[features])
    
    return anomalies == -1  # -1 indica anomalia

def clean_prices(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Limpa e valida os preços dos veículos.
    
    Args:
        df: DataFrame com os dados originais
        
    Returns:
        Tuple contendo (dados_limpos, dados_removidos)
    """
    print("Iniciando limpeza de preços...")
    df_clean = df.copy()
    df_removed = pd.DataFrame()
    
    # 1. Remover preços nulos ou zero
    null_mask = df_clean['price'].isna() | (df_clean['price'] <= 0)
    if null_mask.any():
        print(f"Removendo {null_mask.sum()} registros com preços nulos ou zero")
        df_removed = pd.concat([df_removed, df_clean[null_mask]])
        df_clean = df_clean[~null_mask]
    
    # 2. Processar informações de pagamento nas descrições
    print("Processando informações de pagamento nas descrições...")
    payment_info = df_clean['description'].apply(extract_payment_info)
    payment_mask = payment_info.apply(lambda x: x['has_payment_info'])
    
    # Para registros com informação de pagamento, tentar estimar preço total
    if payment_mask.any():
        print(f"Encontrados {payment_mask.sum()} registros com informações de pagamento")
        estimated_prices = payment_info[payment_mask].apply(estimate_total_price)
        
        # Atualizar preços onde a estimativa é mais realista
        update_mask = payment_mask & (estimated_prices > df_clean['price'])
        if update_mask.any():
            print(f"Atualizando {update_mask.sum()} preços com estimativas de pagamento")
            df_clean.loc[update_mask, 'price'] = estimated_prices[update_mask]
    
    # 3. Aplicar limites por fabricante
    print("Aplicando limites de preço por fabricante...")
    limits = get_manufacturer_price_limits()
    
    for manufacturer, limit in limits.items():
        if manufacturer == 'default':
            continue
            
        mfr_mask = df_clean['manufacturer'].str.lower() == manufacturer
        if not mfr_mask.any():
            continue
            
        invalid_price = (
            (df_clean['price'] < limit['min']) | 
            (df_clean['price'] > limit['max'])
        ) & mfr_mask
        
        if invalid_price.any():
            print(f"Removendo {invalid_price.sum()} registros de {manufacturer} com preços fora dos limites")
            df_removed = pd.concat([df_removed, df_clean[invalid_price]])
            df_clean = df_clean[~invalid_price]
    
    # Aplicar limites padrão para outros fabricantes
    default_limits = limits['default']
    other_mfr_mask = ~df_clean['manufacturer'].str.lower().isin(limits.keys())
    invalid_price = (
        (df_clean['price'] < default_limits['min']) | 
        (df_clean['price'] > default_limits['max'])
    ) & other_mfr_mask
    
    if invalid_price.any():
        print(f"Removendo {invalid_price.sum()} registros de outros fabricantes com preços fora dos limites")
        df_removed = pd.concat([df_removed, df_clean[invalid_price]])
        df_clean = df_clean[~invalid_price]
    
    # 4. Detectar e remover anomalias
    print("Detectando anomalias nos preços...")
    anomalies = detect_price_anomalies(df_clean)
    if anomalies.any():
        print(f"Removendo {anomalies.sum()} registros identificados como anomalias")
        df_removed = pd.concat([df_removed, df_clean[anomalies]])
        df_clean = df_clean[~anomalies]
    
    # Reset index
    df_clean = df_clean.reset_index(drop=True)
    df_removed = df_removed.reset_index(drop=True)
    
    print("\nResumo da limpeza:")
    print(f"Registros originais: {len(df)}")
    print(f"Registros limpos: {len(df_clean)}")
    print(f"Registros removidos: {len(df_removed)}")
    print(f"Porcentagem removida: {(len(df_removed)/len(df)*100):.1f}%")
    
    return df_clean, df_removed

def validate_cleaning(df_clean: pd.DataFrame, df_removed: pd.DataFrame) -> Dict:
    """
    Valida o processo de limpeza e retorna estatísticas.
    
    Args:
        df_clean: DataFrame com dados limpos
        df_removed: DataFrame com dados removidos
        
    Returns:
        Dicionário com estatísticas de validação
    """
    stats = {
        'original_count': len(df_clean) + len(df_removed),
        'cleaned_count': len(df_clean),
        'removed_count': len(df_removed),
        'removed_percentage': (len(df_removed) / (len(df_clean) + len(df_removed))) * 100,
        'price_stats_clean': {
            'mean': df_clean['price'].mean(),
            'median': df_clean['price'].median(),
            'std': df_clean['price'].std(),
            'min': df_clean['price'].min(),
            'max': df_clean['price'].max(),
            'q25': df_clean['price'].quantile(0.25),
            'q75': df_clean['price'].quantile(0.75)
        },
        'price_stats_removed': {
            'mean': df_removed['price'].mean(),
            'median': df_removed['price'].median(),
            'std': df_removed['price'].std(),
            'min': df_removed['price'].min(),
            'max': df_removed['price'].max(),
            'q25': df_removed['price'].quantile(0.25),
            'q75': df_removed['price'].quantile(0.75)
        },
        'manufacturer_stats_clean': df_clean.groupby('manufacturer')['price'].agg(['count', 'mean', 'median']).sort_values('count', ascending=False),
        'manufacturer_stats_removed': df_removed.groupby('manufacturer')['price'].agg(['count', 'mean', 'median']).sort_values('count', ascending=False)
    }
    
    return stats 
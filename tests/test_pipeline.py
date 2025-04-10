import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
from datetime import datetime

from scripts.cleaning.data_cleaner import DataCleaner
from scripts.monitoring.data_monitor import DataMonitor
from scripts.load_to_postgres import PostgresLoader

@pytest.fixture
def sample_data():
    """Cria dados de exemplo para testes."""
    return pd.DataFrame({
        'price': [5000, 10000, -100, 999999999, np.nan],
        'year': [2020, 1800, 2025, 2015, 2010],
        'odometer': [50000, 100000, -1000, 999999, 75000],
        'manufacturer': ['toyota', 'vw', None, 'chevy', 'mercedes'],
        'model': ['camry', 'golf', 'focus', None, 's-class'],
        'condition': ['good', 'invalid', None, 'excellent', 'new'],
        'fuel': ['gas', 'diesel', None, 'hybrid', 'electric'],
        'state': ['ca', 'ny', 'tx', 'fl', 'wa']
    })

@pytest.fixture
def config():
    """Carrega configuração de teste."""
    with open("config/data_cleaning.yaml", 'r') as f:
        return yaml.safe_load(f)

def test_data_cleaner(sample_data, config):
    """Testa a limpeza de dados."""
    cleaner = DataCleaner(
        input_path="",
        output_path="data/cleansed/test.parquet",
        config=config['data_quality']
    )
    
    # Testar limpeza de dados numéricos
    df_numeric = cleaner.clean_numeric_columns(sample_data)
    assert df_numeric['price'].between(100, 1000000).all()
    assert df_numeric['year'].between(1900, datetime.now().year + 1).all()
    assert df_numeric['odometer'].between(0, 1000000).all()
    
    # Testar limpeza de dados categóricos
    df_cat = cleaner.clean_categorical_columns(sample_data)
    assert df_cat['manufacturer'].isin(['toyota', 'volkswagen', 'chevrolet', 'mercedes-benz']).all()
    assert df_cat['condition'].isin(['new', 'excellent', 'good']).all()
    assert df_cat['fuel'].isin(['gas', 'diesel', 'hybrid', 'electric']).all()

def test_data_monitor(sample_data, config):
    """Testa o monitoramento de dados."""
    monitor = DataMonitor(config_path="config/data_cleaning.yaml")
    
    # Testar cálculo de métricas
    metrics = monitor.calculate_metrics(
        sample_data,
        numeric_columns=['price', 'year', 'odometer'],
        categorical_columns=['manufacturer', 'model', 'condition', 'fuel']
    )
    
    assert 'numeric_metrics' in metrics
    assert 'categorical_metrics' in metrics
    assert 'price' in metrics['numeric_metrics']
    assert 'manufacturer' in metrics['categorical_metrics']
    
    # Testar detecção de drift
    reference_data = sample_data.copy()
    reference_data['price'] = reference_data['price'] * 1.5  # Simular drift
    
    drift_metrics = monitor.detect_drift(sample_data, reference_data)
    assert 'numeric_drift' in drift_metrics
    assert 'price' in drift_metrics['numeric_drift']
    assert drift_metrics['numeric_drift']['price']['has_drift'] == True

def test_postgres_loader(sample_data, config):
    """Testa o carregador PostgreSQL."""
    loader = PostgresLoader(
        input_path="",
        table_name="test_cars",
        schema="public"
    )
    
    # Testar geração de tipos SQL
    sql_types = loader._get_sql_dtypes(sample_data)
    assert 'price' in sql_types
    assert 'manufacturer' in sql_types
    
    # Testar validação
    validation = loader.validate_load()
    assert 'total_rows' in validation
    assert 'null_counts' in validation

def test_end_to_end(sample_data, config, tmp_path):
    """Testa o pipeline completo."""
    # Salvar dados de exemplo
    sample_path = tmp_path / "sample.csv"
    sample_data.to_csv(sample_path, index=False)
    
    # Configurar caminhos temporários
    config['storage']['cleansed_data'] = str(tmp_path / "cleansed")
    config['storage']['metrics'] = str(tmp_path / "metrics")
    config['storage']['reference_data'] = str(tmp_path / "reference")
    
    # Executar pipeline
    from scripts.pipeline.cars_etl import cars_etl_pipeline
    result = cars_etl_pipeline(
        input_path=str(sample_path),
        config_path="config/data_cleaning.yaml"
    )
    
    assert result['status'] == 'success'
    assert 'raw_metrics' in result
    assert 'clean_metrics' in result
    
    # Verificar arquivos gerados
    assert (tmp_path / "cleansed").exists()
    assert (tmp_path / "metrics").exists()
    assert len(list((tmp_path / "metrics").glob("*.json"))) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
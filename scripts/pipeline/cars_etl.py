from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta, datetime
import pandas as pd
from pathlib import Path
import logging
import sys
import yaml
import json
import os

# Garantir que o root do projeto esteja no path
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

# Importar classes customizadas
from scripts.cleaning.data_cleaner import DataCleaner
from scripts.monitoring.data_monitor import DataMonitor
from scripts.load_to_postgres import PostgresLoader
from src.etl.ge_validation import validate_raw, validate_clean

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=24))
def load_config(config_path: str = "config/data_cleaning.yaml") -> dict:
    """Carrega configurações do pipeline."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

@task(retries=3, retry_delay_seconds=30)
def extract_data(config: dict) -> pd.DataFrame:
    """Extrai dados do arquivo CSV."""
    input_file = os.path.join(config['storage']['raw_data'], 'used_cars.csv')
    logger.info(f"Lendo arquivo: {input_file}")
    
    df = pd.read_csv(input_file)
    
    # Converter ID para BIGINT
    df['id'] = pd.to_numeric(df['id'], errors='coerce')
    
    logger.info(f"Dados extraídos com sucesso. Shape: {df.shape}")
    return df

@task
def clean_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Limpa e valida os dados."""
    cleaner = DataCleaner(
        input_path="",  # Não usado pois passamos o DataFrame
        output_path=config['storage']['cleansed_data'],
        config=config['data_quality']
    )
    
    # Aplicar limpeza
    df_clean = df.pipe(cleaner.clean_numeric_columns)\
                 .pipe(cleaner.clean_categorical_columns)\
                 .pipe(cleaner.clean_date_columns)\
                 .pipe(cleaner.remove_duplicates)
    
    logger.info("Limpeza de dados concluída")
    return df_clean

@task
def calculate_metrics(
    df: pd.DataFrame,
    stage: str,
    config: dict
) -> dict:
    """Calcula métricas de qualidade dos dados."""
    monitor = DataMonitor(config_path="config/data_cleaning.yaml")
    
    metrics = monitor.calculate_metrics(
        df,
        numeric_columns=list(config['data_quality']['validation_rules'].keys()),
        categorical_columns=list(config['data_quality']['categorical_mappings'].keys())
    )
    
    # Adicionar informações do estágio
    metrics['stage'] = stage
    
    # Salvar métricas
    metrics_path = Path(config['storage']['metrics']) / f"{stage}_metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    return metrics

@task
def detect_data_drift(
    current_data: pd.DataFrame,
    config: dict
) -> dict:
    """Detecta drift nos dados."""
    monitor = DataMonitor(config_path="config/data_cleaning.yaml")
    
    try:
        drift_metrics = monitor.detect_drift(current_data)
        
        # Salvar métricas de drift
        drift_path = Path(config['storage']['metrics']) / "drift_metrics.json"
        drift_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(drift_path, 'w') as f:
            json.dump(drift_metrics, f, indent=2)
        
        return drift_metrics
        
    except Exception as e:
        logger.warning(f"Erro ao detectar drift: {str(e)}")
        return None

@task
def load_to_warehouse(df: pd.DataFrame, config: dict) -> None:
    """Carrega dados limpos no banco de dados."""
    logger.info("Iniciando carregamento no banco de dados")
    
    # Criar loader
    loader = PostgresLoader(
        input_path="",  # Não usado pois passamos o DataFrame
        table_name=config['database']['tables']['cars'],
        schema=config['database']['schema']
    )
    
    # Garantir que o ID seja BIGINT
    df['id'] = df['id'].astype('int64')
    
    # Carregar dados
    loader.load_data(df)
    
    logger.info("Dados carregados com sucesso no banco de dados")

@task(name="ge_validate_raw")
def ge_validate_raw_task(df: pd.DataFrame) -> bool:
    """
    Valida dados brutos com Great Expectations.

    Falhas são logadas como warning — o pipeline NÃO é interrompido por padrão.
    Para bloquear o pipeline em caso de falha, altere raise_on_failure=True.
    """
    logger.info("[GE] Iniciando validação de dados brutos (%d registros)…", len(df))
    passed = validate_raw(df, raise_on_failure=False)
    if not passed:
        logger.warning(
            "[GE] Suite 'raw_cars_suite' reportou falhas. "
            "Verifique gx/uncommitted/validations/ para detalhes."
        )
    return passed


@task(name="ge_validate_clean")
def ge_validate_clean_task(df: pd.DataFrame) -> bool:
    """
    Valida dados limpos com Great Expectations.

    Falhas aqui são mais críticas — dados não conformes não devem ir para o DW.
    raise_on_failure=True interrompe o pipeline se a suite falhar.
    """
    logger.info("[GE] Iniciando validação de dados limpos (%d registros)…", len(df))
    passed = validate_clean(df, raise_on_failure=True)
    return passed


@task
def save_reference_data(
    df: pd.DataFrame,
    config: dict
) -> None:
    """Salva uma cópia dos dados como referência para detecção de drift."""
    reference_path = Path(config['storage']['reference_data']) / "used_cars_reference.parquet"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_parquet(reference_path)
    logger.info(f"Dados de referência salvos em {reference_path}")

@flow(name="cars_etl")
def cars_etl_pipeline(
    input_path: str = "data/raw/used_cars.csv",
    config_path: str = "config/data_cleaning.yaml"
):
    """Pipeline principal de ETL."""
    try:
        # Carregar configurações
        config = load_config(config_path)
        
        # ── Extract ──────────────────────────────────────────────────────────
        df_raw = extract_data(config)
        raw_metrics = calculate_metrics(df_raw, "raw", config)

        # ── Validate raw (GE) ─────────────────────────────────────────────────
        # Falhas aqui são warnings — não interrompem o pipeline
        raw_ge_passed = ge_validate_raw_task(df_raw)

        # ── Transform ─────────────────────────────────────────────────────────
        df_clean = clean_data(df_raw, config)
        clean_metrics = calculate_metrics(df_clean, "clean", config)

        # ── Validate clean (GE) ───────────────────────────────────────────────
        # Falhas aqui interrompem o pipeline (dados não conformes não são carregados)
        clean_ge_passed = ge_validate_clean_task(df_clean)

        # ── Detect drift ──────────────────────────────────────────────────────
        drift_metrics = detect_data_drift(df_clean, config)

        # ── Load ──────────────────────────────────────────────────────────────
        load_to_warehouse(df_clean, config)

        # ── Save reference data ───────────────────────────────────────────────
        reference_path = Path(config['monitoring']['drift_detection']['reference_data'])
        if not reference_path.exists():
            save_reference_data(df_clean, config)

        logger.info("Pipeline executado com sucesso!")

        return {
            "status": "success",
            "raw_metrics": raw_metrics,
            "clean_metrics": clean_metrics,
            "drift_metrics": drift_metrics,
            "ge_raw_passed": raw_ge_passed,
            "ge_clean_passed": clean_ge_passed,
        }
        
    except Exception as e:
        logger.error(f"Erro no pipeline: {str(e)}")
        raise

if __name__ == "__main__":
    # Executar pipeline
    result = cars_etl_pipeline() 
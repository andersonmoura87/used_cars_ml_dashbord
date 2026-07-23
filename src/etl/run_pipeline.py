import logging
from datetime import datetime
import json
from pathlib import Path

from src.etl.extract import extract_data
from src.etl.ge_validation import validate_clean, validate_raw
from src.etl.transform import transform_data
from src.etl.load import load_data
from src.database.connection import test_connection
from src.etl.lineage import (
    LineageClient,
    RAW_CARS_DATASET,
    CLEAN_CARS_DATASET,
    MANUFACTURER_STATS_DATASET,
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def save_metadata(metadata, step):
    """Salva os metadados de cada etapa do pipeline."""
    try:
        # Criar diretório de metadados se não existir
        metadata_dir = Path('logs/metadata')
        metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Nome do arquivo com timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{step}_{timestamp}.json"
        
        # Salvar metadados
        with open(metadata_dir / filename, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Metadados de {step} salvos em {filename}")
    except Exception as e:
        logger.error(f"Erro ao salvar metadados de {step}: {str(e)}")

def run_pipeline():
    """Executa o pipeline ETL completo com rastreamento de linhagem (OpenLineage)."""
    pipeline_start = datetime.now()
    logger.info("Iniciando pipeline ETL")

    # UCM-24: inicializar cliente de linhagem
    lineage = LineageClient(job_name="etl_run_pipeline")

    run_id = lineage.start(
        inputs=[RAW_CARS_DATASET],
        outputs=[CLEAN_CARS_DATASET, MANUFACTURER_STATS_DATASET],
        description=(
            "Pipeline ETL completo: extração → validação GE → transformação → carga PostgreSQL. "
            "Input: used_cars.csv  |  Output: tabelas cars + manufacturer_stats"
        ),
    )

    try:
        # Testar conexão com o banco
        if not test_connection():
            raise Exception("Não foi possível conectar ao banco de dados")

        # Extração
        logger.info("Iniciando etapa de extração")
        df, extract_metadata = extract_data()
        save_metadata(extract_metadata, 'extract')

        # Validação GE — dados brutos (não-bloqueante: warning apenas)
        logger.info("Iniciando validação de dados brutos (Great Expectations)")
        raw_ge_passed = validate_raw(df, raise_on_failure=False)
        save_metadata({"ge_suite": "raw_cars_suite", "passed": raw_ge_passed}, 'ge_raw')

        # Transformação
        logger.info("Iniciando etapa de transformação")
        df_clean, df_removed, market_stats, transform_metadata = transform_data(df)
        save_metadata(transform_metadata, 'transform')

        # Validação GE — dados limpos (bloqueante: interrompe se dados não conformes)
        logger.info("Iniciando validação de dados limpos (Great Expectations)")
        validate_clean(df_clean, raise_on_failure=True)
        save_metadata({"ge_suite": "clean_cars_suite", "passed": True}, 'ge_clean')

        # Carregamento
        logger.info("Iniciando etapa de carregamento")
        load_metadata = load_data(df_clean, market_stats)
        save_metadata(load_metadata, 'load')

        # Metadados do pipeline
        pipeline_end = datetime.now()
        pipeline_metadata = {
            'pipeline_start': pipeline_start.isoformat(),
            'pipeline_end': pipeline_end.isoformat(),
            'duration_seconds': (pipeline_end - pipeline_start).total_seconds(),
            'total_input_records': len(df),
            'total_clean_records': len(df_clean),
            'total_removed_records': len(df_removed),
            'total_market_stats': len(market_stats),
            'ge_raw_passed': raw_ge_passed,
            'ge_clean_passed': True,
            'lineage_run_id': run_id,
        }
        save_metadata(pipeline_metadata, 'pipeline')

        # UCM-24: emitir COMPLETE com schema final das saídas
        clean_out = dict(CLEAN_CARS_DATASET)
        clean_out["fields"] = list(clean_out.get("fields", [])) + [
            {"name": "row_count", "type": "INTEGER"},
        ]
        lineage.complete(run_id, outputs=[clean_out, MANUFACTURER_STATS_DATASET])

        # UCM-22 / UCM-26: métricas + alerta (opcional — não quebra se ausentes)
        try:
            from src.api.telemetry import record_etl_run
            record_etl_run("success")
        except Exception:
            pass

        logger.info("Pipeline ETL concluído com sucesso (lineage run_id=%s)", run_id)
        return True

    except Exception as exc:
        logger.error("Erro no pipeline ETL: %s", str(exc))
        lineage.fail(run_id, error=str(exc))
        try:
            from src.api.telemetry import record_etl_run
            record_etl_run("failure")
        except Exception:
            pass
        return False

if __name__ == "__main__":
    import sys
    sys.exit(0 if run_pipeline() else 1)

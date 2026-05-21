"""
used_cars.etl — re-exporta os módulos canônicos de ETL.
Shim de compatibilidade: qualquer import de src.etl.* ainda funciona.
"""
from src.etl.extract import extract_data
from src.etl.transform import transform_data
from src.etl.load import load_data
from src.etl.ge_validation import validate_raw, validate_clean

__all__ = [
    "extract_data",
    "transform_data",
    "load_data",
    "validate_raw",
    "validate_clean",
]

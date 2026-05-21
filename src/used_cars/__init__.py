"""
used_cars — pacote canônico do projeto (src-layout).

Convenção de imports para código novo:
    from used_cars.etl.extract import extract_data
    from used_cars.api.main import app
    from used_cars.models.price_model import AdvancedPriceModel

Imports legados (src.etl.*, src.api.*, etc.) continuam funcionando
por compatibilidade — serão migrados progressivamente.
"""
__version__ = "0.2.0"

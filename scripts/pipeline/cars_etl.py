#!/usr/bin/env python
"""
DEPRECATED — stub → pipeline canônico (UCM-27).

Não reimplementa extract/transform/load. Qualquer chamada delega a:
    python -m src.etl.run_pipeline

Ver docs/ETL.md.
"""
from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

warnings.warn(
    "scripts.pipeline.cars_etl está DEPRECATED (UCM-27). "
    "Use: python -m src.etl.run_pipeline  — ver docs/ETL.md",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)


def cars_etl_pipeline(*_args, **_kwargs) -> bool:
    """Redirect fino para src.etl.run_pipeline (sem DataCleaner/PostgresLoader)."""
    from src.etl.run_pipeline import run_pipeline

    logger.warning(
        "cars_etl_pipeline stub — delegando a src.etl.run_pipeline (canônico)"
    )
    return bool(run_pipeline())


if __name__ == "__main__":
    sys.exit(0 if cars_etl_pipeline() else 1)

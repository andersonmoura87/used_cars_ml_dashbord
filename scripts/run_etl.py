#!/usr/bin/env python
"""
CLI de ETL — wrapper fino sobre o pipeline canônico.

DEPRECATED como implementação própria (API incompatível com transform_data).
Agora delega para: python -m src.etl.run_pipeline

Uso:
    python scripts/run_etl.py
    run-etl   # entry point pyproject.toml
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

# Garantir root no path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    warnings.warn(
        "scripts.run_etl é um wrapper. Use: python -m src.etl.run_pipeline "
        "(pipeline canônico com GE + lineage + load ORM). Ver docs/ETL.md",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.etl.run_pipeline import run_pipeline

    ok = run_pipeline()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

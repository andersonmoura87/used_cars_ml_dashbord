#!/usr/bin/env python
"""
Treina o AdvancedPriceModel e persiste o artefato em models/.

Uso básico:
    python scripts/train_model.py
    python scripts/train_model.py --data data/processed/cars_abt.csv
    python scripts/train_model.py --validation full  # sem time-series CV
    python scripts/train_model.py --force            # retreina mesmo se já existir

Com MLflow (requer MLFLOW_TRACKING_URI no ambiente):
    MLFLOW_TRACKING_URI=http://localhost:5000 python scripts/train_model.py --force
    python scripts/train_model.py --mlflow-experiment my_exp --mlflow-run-name baseline_v1

Artefatos gerados:
    models/price_model_{timestamp}.joblib        ← versão versionada
    models/price_model_latest.joblib             ← ponteiro para a versão mais recente
    models/price_model_{timestamp}_meta.json     ← metadados do run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.models.price_model import AdvancedPriceModel  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("train_model")

CATEGORICAL_FEATURES = [
    "manufacturer", "model", "condition",
    "fuel", "transmission", "drive", "type", "paint_color", "state",
]
NUMERICAL_FEATURES = ["year", "odometer", "vehicle_age"]
TARGET = "price"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Treina e persiste o modelo de preços.")
    p.add_argument(
        "--data",
        default=str(ROOT / "data" / "processed" / "cars_abt.csv"),
        help="Caminho para o CSV/Parquet de treino",
    )
    p.add_argument(
        "--models-dir",
        default=str(ROOT / "models"),
        help="Diretório para salvar artefatos do modelo",
    )
    p.add_argument(
        "--validation",
        choices=["time_series", "full"],
        default="time_series",
        help="Método de validação (padrão: time_series)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Retreina mesmo que já exista um modelo salvo",
    )
    p.add_argument(
        "--tag",
        default="",
        help="Tag opcional para o nome do arquivo (ex: 'v2', 'prod')",
    )
    p.add_argument(
        "--mlflow-experiment",
        default=os.getenv("MLFLOW_EXPERIMENT_NAME", "used_cars_price_model"),
        help="Nome do experimento MLflow",
    )
    p.add_argument(
        "--mlflow-run-name",
        default=None,
        help="Nome descritivo do run MLflow (auto-gerado se omitido)",
    )
    return p.parse_args()


def load_dataset(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        logger.error("Arquivo de dados não encontrado: %s", p)
        sys.exit(1)
    if p.suffix == ".parquet":
        df = pd.read_parquet(p)
    else:
        df = pd.read_csv(p)
    logger.info("Dataset carregado: %d registros, %d colunas", len(df), len(df.columns))
    return df


def main() -> None:
    args = parse_args()
    models_dir = Path(args.models_dir)
    latest = models_dir / "price_model_latest.joblib"

    if latest.exists() and not args.force:
        logger.info(
            "Modelo já existe em '%s'. Use --force para retreinar.", latest
        )
        sys.exit(0)

    df = load_dataset(args.data)

    # manter apenas colunas disponíveis
    cat_feats = [c for c in CATEGORICAL_FEATURES if c in df.columns]
    num_feats = [c for c in NUMERICAL_FEATURES if c in df.columns]
    required = cat_feats + num_feats + [TARGET]
    df = df[required].dropna(subset=[TARGET])

    logger.info(
        "Features: categoricas=%s | numericas=%s | target=%s",
        cat_feats, num_feats, TARGET,
    )

    model = AdvancedPriceModel(
        categorical_features=cat_feats,
        numerical_features=num_feats,
        target=TARGET,
    )

    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI")
    if mlflow_uri:
        logger.info("MLflow habilitado — URI: %s  experimento: %s", mlflow_uri, args.mlflow_experiment)
    else:
        logger.info("MLFLOW_TRACKING_URI não definido — rodando sem tracking")

    logger.info("Iniciando treino (validacao=%s)…", args.validation)
    metrics = model.train(
        df,
        validation_method=args.validation,
        mlflow_experiment=args.mlflow_experiment,
        mlflow_run_name=args.mlflow_run_name,
        mlflow_tags={"triggered_by": "train_model.py", "tag": args.tag or "default"},
    )

    logger.info("Métricas de validação:")
    for k, v in metrics.items():
        logger.info("  %-8s %.4f", k, v)

    saved_path = model.save(models_dir=models_dir, tag=args.tag)
    logger.info("Artefato salvo em: %s", saved_path)

    # exibe resumo final
    summary = {
        "artifact": str(saved_path),
        "metrics": metrics,
        "features": {"categorical": cat_feats, "numerical": num_feats},
        "training_records": len(df),
    }
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

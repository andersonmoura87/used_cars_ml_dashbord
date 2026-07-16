#!/usr/bin/env python
"""
Detecção de data drift para decidir se retreinamento é necessário.

Compara a distribuição atual (data/processed/cars_abt.csv) com uma
referência salva em data/quality/drift_reference.parquet.

Métricas calculadas:
  - KS test (Kolmogorov-Smirnov) para features numéricas
  - PSI (Population Stability Index) para features categóricas
  - Drift score agregado: média ponderada dos p-values / PSI

Critérios de drift:
  - KS p-value < threshold_ks  (padrão 0.05)   → drift numérico
  - PSI > threshold_psi        (padrão 0.20)   → drift categórico

Saídas:
  - JSON:   data/quality/drift_report_<timestamp>.json
  - GITHUB_OUTPUT: drift_detected=true|false, drift_score=<float>
  - Exit 0 sempre (não bloqueia CI); use --fail-on-drift para bloquear

Uso:
    python scripts/check_drift.py
    python scripts/check_drift.py --current data/processed/cars_abt.csv
    python scripts/check_drift.py --save-reference          # salva referência nova
    python scripts/check_drift.py --fail-on-drift           # exit 1 se drift > threshold
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from datetime import timezone
from scipy import stats

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("check_drift")

NUMERICAL_FEATURES   = ["year", "odometer", "vehicle_age", "price"]
CATEGORICAL_FEATURES = ["manufacturer", "condition", "fuel", "transmission", "drive", "type", "state"]

DEFAULT_CURRENT   = ROOT / "data" / "processed" / "cars_abt.csv"
DEFAULT_REFERENCE = ROOT / "data" / "quality" / "drift_reference.parquet"
DEFAULT_REPORT_DIR = ROOT / "data" / "quality"


# ── KS test ──────────────────────────────────────────────────────────────────

def _ks_test(ref: pd.Series, cur: pd.Series) -> dict:
    """Kolmogorov-Smirnov test para features numéricas."""
    ref_clean = ref.dropna()
    cur_clean = cur.dropna()
    if len(ref_clean) < 10 or len(cur_clean) < 10:
        return {"statistic": None, "p_value": None, "drift": False, "reason": "insufficient_data"}

    result = stats.ks_2samp(ref_clean.values, cur_clean.values)
    return {
        "statistic": round(float(result.statistic), 6),
        "p_value":   round(float(result.pvalue), 6),
        "drift":     bool(result.pvalue < 0.05),
        "reason":    "ks_pvalue_below_threshold" if result.pvalue < 0.05 else "ok",
    }


# ── PSI ──────────────────────────────────────────────────────────────────────

def _psi(ref: pd.Series, cur: pd.Series, eps: float = 1e-4) -> dict:
    """Population Stability Index para features categóricas."""
    categories = set(ref.dropna().unique()) | set(cur.dropna().unique())
    n_ref = len(ref.dropna())
    n_cur = len(cur.dropna())
    if n_ref == 0 or n_cur == 0:
        return {"psi": None, "drift": False, "reason": "insufficient_data"}

    psi_total = 0.0
    details: list[dict] = []
    for cat in categories:
        p_ref = (ref == cat).sum() / n_ref + eps
        p_cur = (cur == cat).sum() / n_cur + eps
        psi_cat = (p_cur - p_ref) * np.log(p_cur / p_ref)
        psi_total += psi_cat
        details.append({"category": str(cat), "psi": round(float(psi_cat), 6)})

    # ordena por PSI descendente para destacar as categorias mais instáveis
    details.sort(key=lambda x: abs(x["psi"]), reverse=True)
    return {
        "psi":     round(float(psi_total), 6),
        "drift":   bool(psi_total > 0.20),
        "reason":  "psi_above_threshold" if psi_total > 0.20 else "ok",
        "top_categories": details[:5],
    }


# ── Agregação ─────────────────────────────────────────────────────────────────

def _aggregate_drift(
    numerical_results: dict[str, dict],
    categorical_results: dict[str, dict],
    threshold_ks: float,
    threshold_psi: float,
) -> tuple[bool, float, list[str]]:
    """
    Retorna (drift_detected, drift_score, drifted_features).

    drift_score ∈ [0, 1]:
      - 0   = sem drift em nenhuma feature
      - 1   = drift máximo em todas as features
    """
    drifted: list[str] = []
    scores: list[float] = []

    for feat, result in numerical_results.items():
        p = result.get("p_value")
        if p is None:
            continue
        score = max(0.0, 1.0 - p / threshold_ks) if p < threshold_ks else 0.0
        scores.append(score)
        if result.get("drift"):
            drifted.append(feat)

    for feat, result in categorical_results.items():
        psi = result.get("psi")
        if psi is None:
            continue
        score = min(1.0, psi / threshold_psi) if psi > threshold_psi else 0.0
        scores.append(score)
        if result.get("drift"):
            drifted.append(feat)

    drift_score = float(np.mean(scores)) if scores else 0.0
    drift_detected = len(drifted) > 0

    return drift_detected, round(drift_score, 4), drifted


# ── Carregamento de dados ─────────────────────────────────────────────────────

def _load_df(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, low_memory=False)


# ── Principal ─────────────────────────────────────────────────────────────────

def check_drift(
    current_path: Path,
    reference_path: Path,
    threshold_ks: float = 0.05,
    threshold_psi: float = 0.20,
    report_dir: Optional[Path] = None,
    save_reference: bool = False,
) -> dict:
    """
    Compara current_path contra reference_path e retorna relatório de drift.
    Se reference_path não existir, salva current como nova referência e retorna sem drift.
    """
    report_dir = report_dir or DEFAULT_REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    current = _load_df(current_path)
    if current is None:
        logger.error("Arquivo atual não encontrado: %s", current_path)
        sys.exit(1)

    reference = _load_df(reference_path)
    if reference is None:
        logger.info(
            "Referência não encontrada — salvando '%s' como nova referência.", current_path
        )
        current.to_parquet(reference_path, index=False)
        return {
            "drift_detected": False,
            "drift_score": 0.0,
            "drifted_features": [],
            "numerical": {},
            "categorical": {},
            "status": "reference_created",
            "message": f"Referência criada a partir de: {current_path}",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    logger.info(
        "Comparando %d registros atuais vs %d de referência",
        len(current), len(reference),
    )

    # ── Análise numérica ──────────────────────────────────────────────────────
    numerical_results: dict[str, dict] = {}
    for feat in NUMERICAL_FEATURES:
        if feat in current.columns and feat in reference.columns:
            numerical_results[feat] = _ks_test(reference[feat], current[feat])
            status = "DRIFT" if numerical_results[feat]["drift"] else "OK"
            logger.info("  [NUM] %-15s %s  p=%.4f", feat, status,
                        numerical_results[feat].get("p_value") or -1)

    # ── Análise categórica ────────────────────────────────────────────────────
    categorical_results: dict[str, dict] = {}
    for feat in CATEGORICAL_FEATURES:
        if feat in current.columns and feat in reference.columns:
            categorical_results[feat] = _psi(reference[feat], current[feat])
            status = "DRIFT" if categorical_results[feat]["drift"] else "OK"
            logger.info("  [CAT] %-15s %s  PSI=%.4f", feat, status,
                        categorical_results[feat].get("psi") or -1)

    # ── Agregação ─────────────────────────────────────────────────────────────
    drift_detected, drift_score, drifted_features = _aggregate_drift(
        numerical_results, categorical_results, threshold_ks, threshold_psi
    )

    report = {
        "drift_detected":   drift_detected,
        "drift_score":      drift_score,
        "drifted_features": drifted_features,
        "numerical":        numerical_results,
        "categorical":      categorical_results,
        "thresholds":       {"ks_pvalue": threshold_ks, "psi": threshold_psi},
        "data_stats": {
            "current_rows":   len(current),
            "reference_rows": len(reference),
            "current_path":   str(current_path),
            "reference_path": str(reference_path),
        },
        "status": "drift_detected" if drift_detected else "no_drift",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Salvar relatório JSON
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"drift_report_{ts}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Relatório salvo em: %s", report_path)

    if save_reference:
        logger.info("Salvando nova referência: %s", reference_path)
        current.to_parquet(reference_path, index=False)

    return report


def _write_github_outputs(report: dict) -> None:
    """Escreve drift_detected e drift_score no GITHUB_OUTPUT."""
    github_output = os.getenv("GITHUB_OUTPUT")
    if not github_output:
        return
    with open(github_output, "a") as f:
        f.write(f"drift_detected={'true' if report['drift_detected'] else 'false'}\n")
        f.write(f"drift_score={report['drift_score']}\n")
        f.write(f"drifted_features={','.join(report['drifted_features'])}\n")

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        icon = ":warning:" if report.get("drift_detected") else ":white_check_mark:"
        with open(summary, "a") as f:
            f.write(f"## {icon} Data Drift Report\n\n")
            f.write(f"**Status:** {report.get('status', 'N/A')}  \n")
            f.write(f"**Drift Score:** {report.get('drift_score', 0.0):.4f}  \n\n")
            drifted = report.get("drifted_features") or []
            if drifted:
                f.write(f"**Features com drift:** {', '.join(drifted)}\n\n")
            numerical = report.get("numerical") or {}
            if numerical:
                f.write("### Numéricas (KS test)\n\n")
                f.write("| Feature | p-value | Estatística | Drift |\n")
                f.write("|---------|---------|-------------|-------|\n")
                for feat, r in numerical.items():
                    pv = f"{r['p_value']:.4f}" if r.get("p_value") is not None else "N/A"
                    st = f"{r['statistic']:.4f}" if r.get("statistic") is not None else "N/A"
                    dr = ":x:" if r.get("drift") else ":white_check_mark:"
                    f.write(f"| {feat} | {pv} | {st} | {dr} |\n")
            categorical = report.get("categorical") or {}
            if categorical:
                f.write("\n### Categóricas (PSI)\n\n")
                f.write("| Feature | PSI | Drift |\n")
                f.write("|---------|-----|-------|\n")
                for feat, r in categorical.items():
                    psi = f"{r['psi']:.4f}" if r.get("psi") is not None else "N/A"
                    dr  = ":x:" if r.get("drift") else ":white_check_mark:"
                    f.write(f"| {feat} | {psi} | {dr} |\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Detecção de data drift para retreinamento.")
    p.add_argument("--current",   default=str(DEFAULT_CURRENT),   help="CSV/Parquet com dados atuais")
    p.add_argument("--reference", default=str(DEFAULT_REFERENCE), help="Parquet de referência")
    p.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Diretório para relatórios")
    p.add_argument("--threshold-ks",  type=float, default=0.05, help="p-value mínimo KS (padrão 0.05)")
    p.add_argument("--threshold-psi", type=float, default=0.20, help="PSI máximo (padrão 0.20)")
    p.add_argument("--save-reference", action="store_true", help="Salvar current como nova referência")
    p.add_argument("--fail-on-drift",  action="store_true", help="Sair com exit 1 se drift detectado")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    report = check_drift(
        current_path=Path(args.current),
        reference_path=Path(args.reference),
        threshold_ks=args.threshold_ks,
        threshold_psi=args.threshold_psi,
        report_dir=Path(args.report_dir),
        save_reference=args.save_reference,
    )

    _write_github_outputs(report)

    verdict = "DRIFT DETECTADO" if report["drift_detected"] else "SEM DRIFT"
    logger.info("Veredicto: %s  (score=%.4f)", verdict, report["drift_score"])
    if report["drifted_features"]:
        logger.info("Features com drift: %s", ", ".join(report["drifted_features"]))

    if args.fail_on_drift and report["drift_detected"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

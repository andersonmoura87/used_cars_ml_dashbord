#!/usr/bin/env python
"""
Orquestrador de retreinamento automático do modelo de preços.

Fluxo completo:
  1. [DRIFT]  Verifica drift nos dados atuais vs. referência
  2. [TRAIN]  Treina novo modelo (forçado, ou apenas se drift detectado)
  3. [REGISTER] Registra versão no MLflow Model Registry (stage: None)
  4. [COMPARE]  Executa champion/challenger via scripts/compare_models.py
  5. [PROMOTE]  Auto-promove para Staging se challenger vencer

Uso:
    # Retreina apenas se drift detectado
    python scripts/retrain.py

    # Força retreinamento independente de drift
    python scripts/retrain.py --force

    # Dry-run: analisa drift e treina, mas não promove automaticamente
    python scripts/retrain.py --dry-run

    # Define o threshold mínimo de melhoria para champion/challenger
    python scripts/retrain.py --min-improvement 0.005

Variáveis de ambiente:
    MLFLOW_TRACKING_URI       — URI do servidor MLflow (opcional)
    MLFLOW_EXPERIMENT_NAME    — nome do experimento (padrão: used_cars_price_model)
    MLFLOW_REGISTERED_MODEL   — nome do modelo no registry
    RETRAIN_DATA_PATH         — caminho para os dados de treino
    RETRAIN_MODELS_DIR        — diretório para salvar artefatos
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("retrain")

DEFAULT_DATA_PATH  = ROOT / "data" / "processed" / "cars_abt.csv"
DEFAULT_MODELS_DIR = ROOT / "models"
DEFAULT_REFERENCE  = ROOT / "data" / "quality" / "drift_reference.parquet"
DEFAULT_REPORT_DIR = ROOT / "data" / "quality"
PYTHON = sys.executable


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list[str], step: str) -> tuple[int, str]:
    """Executa um subprocesso e retorna (exit_code, stdout+stderr combinado)."""
    logger.info("[%s] Executando: %s", step, " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = (result.stdout or "") + (result.stderr or "")
    if output.strip():
        for line in output.strip().splitlines():
            logger.info("[%s] %s", step, line)
    return result.returncode, output


def _write_github_outputs(key: str, value: str) -> None:
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"{key}={value}\n")


def _write_summary(lines: list[str]) -> None:
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("\n".join(lines) + "\n")


# ── Etapas do pipeline ────────────────────────────────────────────────────────

def step_drift(
    data_path: Path,
    reference_path: Path,
    report_dir: Path,
    threshold_ks: float,
    threshold_psi: float,
    force: bool,
) -> tuple[bool, float, list[str]]:
    """
    Executa detecção de drift.
    Retorna (drift_detected, drift_score, drifted_features).
    """
    if force:
        logger.info("[DRIFT] --force ativado — pulando verificação de drift")
        return True, 0.0, []

    if not data_path.exists():
        logger.warning("[DRIFT] Arquivo de dados não encontrado: %s — assumindo drift", data_path)
        return True, 1.0, ["data_not_found"]

    cmd = [
        PYTHON, str(ROOT / "scripts" / "check_drift.py"),
        "--current",       str(data_path),
        "--reference",     str(reference_path),
        "--report-dir",    str(report_dir),
        "--threshold-ks",  str(threshold_ks),
        "--threshold-psi", str(threshold_psi),
    ]
    code, output = _run(cmd, "DRIFT")

    # Tentar ler o relatório mais recente para obter o score
    reports = sorted(report_dir.glob("drift_report_*.json"))
    if reports:
        try:
            with open(reports[-1]) as f:
                report = json.load(f)
            return (
                report.get("drift_detected", False),
                report.get("drift_score", 0.0),
                report.get("drifted_features", []),
            )
        except Exception as exc:
            logger.warning("[DRIFT] Falha ao ler relatório: %s", exc)

    # Fallback: se o script saiu com erro, considera drift
    return code != 0, 0.0, []


def step_train(
    data_path: Path,
    models_dir: Path,
    experiment: str,
    run_name: str,
    tag: str,
) -> tuple[int, str | None]:
    """
    Treina o modelo com --force.
    Retorna (exit_code, artifact_path).
    """
    if not data_path.exists():
        logger.error("[TRAIN] Dados não encontrados: %s", data_path)
        return 1, None

    cmd = [
        PYTHON, str(ROOT / "scripts" / "train_model.py"),
        "--data",            str(data_path),
        "--models-dir",      str(models_dir),
        "--force",
        "--mlflow-experiment", experiment,
        "--mlflow-run-name",   run_name,
        "--tag",               tag,
    ]
    code, output = _run(cmd, "TRAIN")

    # Tentar extrair caminho do artefato do stdout JSON
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                summary = json.loads(line)
                return code, summary.get("artifact")
            except json.JSONDecodeError:
                pass

    return code, None


def step_compare(
    min_improvement: float,
    output_json: Path,
    dry_run: bool,
) -> tuple[bool, str | None]:
    """
    Executa champion/challenger.
    Retorna (challenger_wins, challenger_version).
    """
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not mlflow_uri:
        logger.warning("[COMPARE] MLFLOW_TRACKING_URI não definido — pulando comparação")
        return False, None

    cmd = [
        PYTHON, str(ROOT / "scripts" / "compare_models.py"),
        "--min-improvement", str(min_improvement),
        "--output-json",     str(output_json),
    ]
    if dry_run:
        cmd.append("--dry-run")

    code, _ = _run(cmd, "COMPARE")

    challenger_wins = False
    challenger_version = None
    if output_json.exists():
        try:
            with open(output_json) as f:
                result = json.load(f)
            challenger_wins    = result.get("challenger_wins", False)
            challenger_version = result.get("challenger", {}).get("version")
        except Exception as exc:
            logger.warning("[COMPARE] Falha ao ler resultado: %s", exc)

    return challenger_wins, challenger_version


def step_promote(version: str | None) -> int:
    """Auto-promove challenger para Staging."""
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not mlflow_uri:
        logger.warning("[PROMOTE] MLFLOW_TRACKING_URI não definido — pulando promoção")
        return 0

    cmd = [
        PYTHON, str(ROOT / "scripts" / "promote_model.py"),
        "--to", "Staging",
    ]
    if version:
        cmd += ["--version", str(version)]

    code, _ = _run(cmd, "PROMOTE")
    return code


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pipeline de retreinamento automático.")
    p.add_argument("--data",           default=os.getenv("RETRAIN_DATA_PATH",   str(DEFAULT_DATA_PATH)))
    p.add_argument("--models-dir",     default=os.getenv("RETRAIN_MODELS_DIR",  str(DEFAULT_MODELS_DIR)))
    p.add_argument("--reference",      default=str(DEFAULT_REFERENCE))
    p.add_argument("--report-dir",     default=str(DEFAULT_REPORT_DIR))
    p.add_argument("--force",          action="store_true", help="Retreinar independente de drift")
    p.add_argument("--dry-run",        action="store_true", help="Não promove automaticamente")
    p.add_argument("--threshold-ks",   type=float, default=0.05)
    p.add_argument("--threshold-psi",  type=float, default=0.20)
    p.add_argument("--min-improvement",type=float, default=0.001,
                   help="Melhoria mínima no R² para o challenger vencer")
    p.add_argument("--experiment",     default=os.getenv("MLFLOW_EXPERIMENT_NAME", "used_cars_price_model"))
    p.add_argument("--run-name",       default=None, help="Nome do run MLflow (auto-gerado se omitido)")
    p.add_argument("--tag",            default="", help="Tag para o artefato (ex: 'weekly', 'v2')")
    p.add_argument("--save-reference", action="store_true",
                   help="Atualizar referência de drift ao final do treino")
    return p.parse_args()


def main() -> None:
    args      = parse_args()
    started   = datetime.now(timezone.utc)
    data_path = Path(args.data)
    models_dir = Path(args.models_dir)
    reference  = Path(args.reference)
    report_dir = Path(args.report_dir)
    run_name   = args.run_name or f"retrain_{started.strftime('%Y%m%d_%H%M')}"
    tag        = args.tag or started.strftime("%Y%m%d")
    output_json = report_dir / f"comparison_{started.strftime('%Y%m%d_%H%M%S')}.json"

    models_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    summary_lines: list[str] = [
        f"## :arrows_counterclockwise: Pipeline de Retreinamento — {started.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    # ── 1. DRIFT ─────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("ETAPA 1/4 — Detecção de Drift")
    logger.info("=" * 60)
    drift_detected, drift_score, drifted_features = step_drift(
        data_path, reference, report_dir, args.threshold_ks, args.threshold_psi, args.force
    )

    icon_drift = ":warning:" if drift_detected else ":white_check_mark:"
    summary_lines += [
        f"### {icon_drift} 1. Drift",
        f"- **Detectado:** {'Sim' if drift_detected else 'Não'}",
        f"- **Score:** {drift_score:.4f}",
        f"- **Features afetadas:** {', '.join(drifted_features) if drifted_features else '—'}",
        "",
    ]
    _write_github_outputs("drift_detected", "true" if drift_detected else "false")
    _write_github_outputs("drift_score", str(drift_score))

    if not drift_detected:
        logger.info("Sem drift detectado — retreinamento não necessário.")
        _write_summary(summary_lines + ["### :white_check_mark: Retreinamento pulado — sem drift"])
        _write_github_outputs("retrain_triggered", "false")
        _write_github_outputs("challenger_wins",   "false")
        return

    _write_github_outputs("retrain_triggered", "true")

    # ── 2. TRAIN ─────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("ETAPA 2/4 — Treino do Novo Modelo")
    logger.info("=" * 60)
    train_code, artifact_path = step_train(data_path, models_dir, args.experiment, run_name, tag)

    if train_code != 0:
        logger.error("Treino falhou com código %d — abortando", train_code)
        summary_lines.append("### :x: 2. Treino falhou")
        _write_summary(summary_lines)
        sys.exit(train_code)

    summary_lines += [
        "### :white_check_mark: 2. Treino",
        f"- **Artefato:** `{artifact_path or 'models/price_model_latest.joblib'}`",
        f"- **Run name:** `{run_name}`",
        f"- **Tag:** `{tag}`",
        "",
    ]
    logger.info("Treino concluído. Artefato: %s", artifact_path or "models/price_model_latest.joblib")

    # ── 3. CHAMPION/CHALLENGER ────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("ETAPA 3/4 — Champion vs Challenger")
    logger.info("=" * 60)
    challenger_wins, challenger_version = step_compare(
        args.min_improvement, output_json, args.dry_run
    )

    icon_compare = ":white_check_mark:" if challenger_wins else ":x:"
    summary_lines += [
        f"### {icon_compare} 3. Champion vs Challenger",
        f"- **Challenger vence:** {'Sim' if challenger_wins else 'Não'}",
        f"- **Versão challenger:** `{challenger_version or 'N/A'}`",
        "",
    ]
    _write_github_outputs("challenger_wins",   "true" if challenger_wins else "false")
    _write_github_outputs("challenger_version", challenger_version or "")

    # ── 4. PROMOTE ────────────────────────────────────────────────────────────
    if challenger_wins and not args.dry_run:
        logger.info("=" * 60)
        logger.info("ETAPA 4/4 — Promoção para Staging")
        logger.info("=" * 60)
        promote_code = step_promote(challenger_version)
        icon_promote = ":white_check_mark:" if promote_code == 0 else ":x:"
        summary_lines += [
            f"### {icon_promote} 4. Promoção para Staging",
            f"- **Versão:** `{challenger_version or 'latest'}`",
            f"- **Status:** {'OK' if promote_code == 0 else 'Falhou (código ' + str(promote_code) + ')'}",
            "",
        ]
    elif args.dry_run:
        summary_lines += [
            "### :information_source: 4. Promoção",
            "- **Modo dry-run** — promoção não executada.",
            "",
        ]
    else:
        summary_lines += [
            "### :x: 4. Champion mantido",
            "- Challenger não superou o champion — promoção não realizada.",
            "",
        ]

    # ── Referência de drift ───────────────────────────────────────────────────
    if args.save_reference and drift_detected:
        logger.info("Salvando nova referência de drift...")
        cmd = [
            PYTHON, str(ROOT / "scripts" / "check_drift.py"),
            "--current",       str(data_path),
            "--reference",     str(reference),
            "--save-reference",
        ]
        _run(cmd, "SAVE_REF")
        summary_lines.append("- :floppy_disk: **Referência de drift atualizada.**\n")

    # ── Sumário final ─────────────────────────────────────────────────────────
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    summary_lines += [
        "---",
        f"**Duração total:** {elapsed:.1f}s",
        f"**Iniciado em:** {started.strftime('%Y-%m-%d %H:%M:%S UTC')}",
    ]
    _write_summary(summary_lines)

    logger.info("Pipeline finalizado em %.1fs", elapsed)


if __name__ == "__main__":
    main()

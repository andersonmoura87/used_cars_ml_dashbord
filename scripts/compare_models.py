#!/usr/bin/env python
"""
Compara as métricas do modelo challenger (Staging) com o champion (Production).

Fluxo champion/challenger:
    1. Um novo modelo é treinado e registrado automaticamente (stage: None)
    2. Este script compara o challenger (Staging ou versão específica) com o champion (Production)
    3. Se challenger vence → exit 0  (CI pode auto-promover para Staging / criar PR para Production)
    4. Se challenger perde → exit 1  (CI bloqueia a promoção)
    5. Se não há champion → challenger vence automaticamente (bootstrap)

Métricas comparadas (ordem de prioridade):
    R²   — quanto maior, melhor
    RMSE — quanto menor, melhor
    MAE  — quanto menor, melhor

A comparação usa uma margem mínima (--min-improvement) para evitar promoções
por melhorias negligenciáveis.

Uso:
    # Comparar Staging vs Production (caso padrão)
    python scripts/compare_models.py

    # Comparar versão específica vs Production
    python scripts/compare_models.py --challenger-version 5

    # Exigir melhoria mínima de 1% no R² para considerar challenger vencedor
    python scripts/compare_models.py --min-improvement 0.01

    # Apenas exibir métricas sem sair com erro (dry-run)
    python scripts/compare_models.py --dry-run

Variáveis de ambiente:
    MLFLOW_TRACKING_URI     — URI do servidor MLflow (obrigatório)
    MLFLOW_REGISTERED_MODEL — nome do modelo no registry (default: used_cars_price_model)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

try:
    import mlflow
    from mlflow.tracking import MlflowClient
except ImportError:
    print("ERRO: mlflow não instalado. Execute: pip install mlflow")
    sys.exit(1)

DEFAULT_MODEL = "used_cars_price_model"

# Métricas onde "maior é melhor"
HIGHER_IS_BETTER = {"r2", "r2_score"}
# Métricas onde "menor é melhor"
LOWER_IS_BETTER  = {"rmse", "mae", "mse", "loss"}


@dataclass
class ModelMetrics:
    version: str
    stage: str
    run_id: str
    r2: Optional[float]
    rmse: Optional[float]
    mae: Optional[float]
    registered_at: str
    tags: dict = field(default_factory=dict)

    def display(self) -> str:
        r2_s   = f"{self.r2:.4f}"   if self.r2   is not None else "N/A"
        rmse_s = f"{self.rmse:.2f}" if self.rmse is not None else "N/A"
        mae_s  = f"{self.mae:.2f}"  if self.mae  is not None else "N/A"
        return f"v{self.version} [{self.stage}] R²={r2_s}  RMSE={rmse_s}  MAE={mae_s}"


def _get_client() -> MlflowClient:
    uri = os.getenv("MLFLOW_TRACKING_URI")
    if not uri:
        print("ERRO: MLFLOW_TRACKING_URI não definido.")
        sys.exit(1)
    mlflow.set_tracking_uri(uri)
    return MlflowClient()


def _fetch_metrics(client: MlflowClient, version_obj) -> ModelMetrics:
    """Extrai ModelMetrics de um objeto de versão do MLflow Registry."""
    run_id = version_obj.run_id
    ts = datetime.fromtimestamp(
        version_obj.creation_timestamp / 1000
    ).strftime("%Y-%m-%d %H:%M UTC")

    r2 = rmse = mae = None
    try:
        run = client.get_run(run_id)
        m = run.data.metrics
        r2   = m.get("r2")
        rmse = m.get("rmse")
        mae  = m.get("mae")
    except Exception as exc:
        print(f"  AVISO: não foi possível buscar métricas do run {run_id}: {exc}")

    return ModelMetrics(
        version=version_obj.version,
        stage=version_obj.current_stage,
        run_id=run_id,
        r2=r2,
        rmse=rmse,
        mae=mae,
        registered_at=ts,
        tags=dict(version_obj.tags or {}),
    )


def _fetch_champion(client: MlflowClient, model_name: str) -> Optional[ModelMetrics]:
    """Busca o modelo champion atual (stage: Production)."""
    versions = client.get_latest_versions(model_name, stages=["Production"])
    if not versions:
        return None
    return _fetch_metrics(client, versions[0])


def _fetch_challenger(
    client: MlflowClient,
    model_name: str,
    challenger_version: Optional[str],
) -> Optional[ModelMetrics]:
    """Busca o modelo challenger (stage: Staging ou versão específica)."""
    if challenger_version:
        try:
            v = client.get_model_version(model_name, challenger_version)
            return _fetch_metrics(client, v)
        except Exception as exc:
            print(f"ERRO: versão '{challenger_version}' não encontrada: {exc}")
            sys.exit(1)

    versions = client.get_latest_versions(model_name, stages=["Staging"])
    if not versions:
        # Se não há Staging, pega a versão mais recente (stage: None)
        all_versions = client.search_model_versions(f"name='{model_name}'")
        if not all_versions:
            print(f"ERRO: nenhuma versão registrada para '{model_name}'.")
            sys.exit(1)
        latest = sorted(all_versions, key=lambda v: int(v.version))[-1]
        return _fetch_metrics(client, latest)

    return _fetch_metrics(client, versions[0])


def _challenger_wins(
    champion: ModelMetrics,
    challenger: ModelMetrics,
    min_improvement: float,
) -> tuple[bool, list[str]]:
    """
    Retorna (challenger_vence, razoes[]).

    Lógica: o challenger vence se melhorar o R² por pelo menos `min_improvement`
    E não piorar RMSE em mais de 5%.
    """
    reasons: list[str] = []

    # R² — mais alto é melhor
    if champion.r2 is not None and challenger.r2 is not None:
        delta_r2 = challenger.r2 - champion.r2
        pct = delta_r2 / abs(champion.r2) * 100 if champion.r2 != 0 else 0
        if delta_r2 >= min_improvement:
            reasons.append(f"R² melhorou: {champion.r2:.4f} → {challenger.r2:.4f} (+{pct:.2f}%)")
        else:
            reasons.append(f"R² não melhorou suficientemente: {champion.r2:.4f} → {challenger.r2:.4f} ({pct:+.2f}%)")
            return False, reasons

    elif champion.r2 is None and challenger.r2 is not None:
        reasons.append(f"Challenger tem R²={challenger.r2:.4f}; champion sem R² — challenger vence por default")

    # RMSE — mais baixo é melhor (tolerância 5% de regressão)
    if champion.rmse is not None and challenger.rmse is not None:
        delta_rmse = champion.rmse - challenger.rmse
        pct = delta_rmse / champion.rmse * 100 if champion.rmse != 0 else 0
        if delta_rmse >= 0:
            reasons.append(f"RMSE melhorou: {champion.rmse:.2f} → {challenger.rmse:.2f} ({pct:+.2f}%)")
        elif abs(delta_rmse / champion.rmse) > 0.05:
            reasons.append(
                f"RMSE piorou mais de 5%: {champion.rmse:.2f} → {challenger.rmse:.2f} "
                f"({pct:+.2f}%) — challenger REPROVADO"
            )
            return False, reasons
        else:
            reasons.append(
                f"RMSE levemente pior (dentro de 5%): {champion.rmse:.2f} → "
                f"{challenger.rmse:.2f} ({pct:+.2f}%) — aceito"
            )

    return True, reasons


def compare(
    client: MlflowClient,
    model_name: str,
    challenger_version: Optional[str],
    min_improvement: float,
    dry_run: bool,
    output_json: Optional[str],
) -> bool:
    """
    Compara champion vs challenger. Retorna True se challenger vence.
    """
    print(f"\n{'='*60}")
    print(f"  Champion vs Challenger — {model_name}")
    print(f"{'='*60}\n")

    champion   = _fetch_champion(client, model_name)
    challenger = _fetch_challenger(client, model_name, challenger_version)

    if challenger is None:
        print("ERRO: nenhum modelo challenger encontrado.")
        return False

    # Exibir métricas
    if champion:
        print(f"  CHAMPION  : {champion.display()}")
    else:
        print("  CHAMPION  : nenhum modelo em Production (bootstrap)")

    print(f"  CHALLENGER: {challenger.display()}")
    print()

    # Decidir vencedor
    if champion is None:
        challenger_wins = True
        reasons = ["Sem champion em Production — challenger promovido automaticamente (bootstrap)"]
    else:
        challenger_wins, reasons = _challenger_wins(champion, challenger, min_improvement)

    # Exibir raciocínio
    print("  Análise:")
    for r in reasons:
        prefix = "  [OK]" if "melhorou" in r or "bootstrap" in r or "aceito" in r else "  [!!]"
        print(f"  {prefix} {r}")

    print()
    verdict = "CHALLENGER VENCE" if challenger_wins else "CHAMPION MANTIDO"
    print(f"  Veredicto: {verdict}")
    print(f"{'='*60}\n")

    # Persistir resultado (para GitHub Actions summary)
    result = {
        "verdict": verdict,
        "challenger_wins": challenger_wins,
        "model_name": model_name,
        "champion": {
            "version": champion.version if champion else None,
            "stage": champion.stage if champion else None,
            "r2": champion.r2 if champion else None,
            "rmse": champion.rmse if champion else None,
            "mae": champion.mae if champion else None,
        },
        "challenger": {
            "version": challenger.version,
            "stage": challenger.stage,
            "r2": challenger.r2,
            "rmse": challenger.rmse,
            "mae": challenger.mae,
        },
        "reasons": reasons,
        "min_improvement": min_improvement,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }

    if output_json:
        with open(output_json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Resultado salvo em: {output_json}")

    # GitHub Actions summary
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        champ_r2   = f"{champion.r2:.4f}"   if champion and champion.r2   is not None else "N/A"
        champ_rmse = f"{champion.rmse:.2f}" if champion and champion.rmse is not None else "N/A"
        chal_r2   = f"{challenger.r2:.4f}"   if challenger.r2   is not None else "N/A"
        chal_rmse = f"{challenger.rmse:.2f}" if challenger.rmse is not None else "N/A"

        with open(summary, "a") as f:
            icon = ":white_check_mark:" if challenger_wins else ":x:"
            f.write(f"## {icon} Champion vs Challenger — {model_name}\n\n")
            f.write(f"**Veredicto:** {verdict}\n\n")
            f.write("| Modelo | Versão | Stage | R² | RMSE |\n")
            f.write("|--------|--------|-------|----|------|\n")
            champ_ver = champion.version if champion else "—"
            champ_stage = champion.stage if champion else "—"
            f.write(f"| Champion   | v{champ_ver} | {champ_stage} | {champ_r2} | {champ_rmse} |\n")
            f.write(f"| Challenger | v{challenger.version} | {challenger.stage} | {chal_r2} | {chal_rmse} |\n\n")
            f.write("**Análise:**\n")
            for r in reasons:
                f.write(f"- {r}\n")

    # Definir output para GitHub Actions
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"challenger_wins={'true' if challenger_wins else 'false'}\n")
            f.write(f"challenger_version={challenger.version}\n")
            f.write(f"verdict={verdict}\n")

    return challenger_wins


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compara champion (Production) vs challenger (Staging) no MLflow Registry."
    )
    p.add_argument(
        "--model",
        default=os.getenv("MLFLOW_REGISTERED_MODEL", DEFAULT_MODEL),
        help="Nome do modelo no registry",
    )
    p.add_argument(
        "--challenger-version",
        help="Versão específica do challenger (default: mais recente em Staging)",
    )
    p.add_argument(
        "--min-improvement",
        type=float,
        default=0.001,
        help="Melhoria mínima no R² para o challenger vencer (default: 0.001 = 0.1%%)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Exibe comparação sem retornar exit code 1 em caso de derrota",
    )
    p.add_argument(
        "--output-json",
        help="Caminho para salvar o resultado em JSON",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    client = _get_client()

    challenger_wins = compare(
        client=client,
        model_name=args.model,
        challenger_version=args.challenger_version,
        min_improvement=args.min_improvement,
        dry_run=args.dry_run,
        output_json=args.output_json,
    )

    if not args.dry_run and not challenger_wins:
        sys.exit(1)


if __name__ == "__main__":
    main()

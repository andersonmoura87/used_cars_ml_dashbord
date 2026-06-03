#!/usr/bin/env python
"""
Promove um modelo do MLflow Model Registry entre stages.

Fluxo de promoção:
    None → Staging → Production

Uso:
    # Promover versão específica para Staging
    python scripts/promote_model.py --version 3 --to Staging

    # Promover versão específica para Production
    python scripts/promote_model.py --version 3 --to Production

    # Promover o modelo mais recente de Staging → Production
    python scripts/promote_model.py --from-stage Staging --to Production

    # Listar todas as versões do modelo
    python scripts/promote_model.py --list

Variáveis de ambiente:
    MLFLOW_TRACKING_URI     — URI do servidor MLflow (obrigatório)
    MLFLOW_REGISTERED_MODEL — nome do modelo no registry (default: used_cars_price_model)
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

# ── MLflow ────────────────────────────────────────────────────────────────────
try:
    import mlflow
    from mlflow.tracking import MlflowClient
except ImportError:
    print("ERRO: mlflow não instalado. Execute: pip install mlflow")
    sys.exit(1)

DEFAULT_MODEL = "used_cars_price_model"
VALID_STAGES  = ("None", "Staging", "Production", "Archived")


def get_client() -> MlflowClient:
    uri = os.getenv("MLFLOW_TRACKING_URI")
    if not uri:
        print("ERRO: MLFLOW_TRACKING_URI não definido.")
        sys.exit(1)
    mlflow.set_tracking_uri(uri)
    return MlflowClient()


def list_versions(client: MlflowClient, model_name: str) -> None:
    """Exibe todas as versões do modelo com seus stages."""
    print(f"\nModelo: {model_name}")
    print(f"{'Versão':<8} {'Stage':<12} {'Run ID':<36} {'Data':<20} {'Métricas'}")
    print("-" * 100)
    try:
        versions = client.search_model_versions(f"name='{model_name}'")
    except Exception as e:
        print(f"ERRO ao buscar versões: {e}")
        sys.exit(1)

    if not versions:
        print("Nenhuma versão registrada.")
        return

    for v in sorted(versions, key=lambda x: int(x.version)):
        run_id = v.run_id
        ts = datetime.fromtimestamp(v.creation_timestamp / 1000).strftime("%Y-%m-%d %H:%M")

        # Buscar métricas do run
        metrics_str = ""
        try:
            run = client.get_run(run_id)
            m = run.data.metrics
            r2   = m.get("r2", None)
            rmse = m.get("rmse", None)
            if r2 is not None and rmse is not None:
                metrics_str = f"R²={r2:.4f}  RMSE={rmse:.0f}"
        except Exception:
            pass

        print(f"{v.version:<8} {v.current_stage:<12} {run_id:<36} {ts:<20} {metrics_str}")


def promote(
    client: MlflowClient,
    model_name: str,
    version: str | None,
    from_stage: str | None,
    to_stage: str,
    archive_existing: bool,
) -> None:
    """Promove a versão especificada (ou a mais recente de from_stage) para to_stage."""
    if to_stage not in VALID_STAGES:
        print(f"ERRO: Stage inválido '{to_stage}'. Válidos: {VALID_STAGES}")
        sys.exit(1)

    # Resolver qual versão promover
    if version:
        target_version = version
    elif from_stage:
        versions = client.get_latest_versions(model_name, stages=[from_stage])
        if not versions:
            print(f"ERRO: Nenhuma versão em '{from_stage}' para o modelo '{model_name}'.")
            sys.exit(1)
        target_version = versions[0].version
        print(f"Versão mais recente em {from_stage}: v{target_version}")
    else:
        print("ERRO: Especifique --version ou --from-stage.")
        sys.exit(1)

    # Arquivar versões existentes em Production antes de promover (evita conflitos)
    if to_stage == "Production" and archive_existing:
        existing = client.get_latest_versions(model_name, stages=["Production"])
        for ev in existing:
            if ev.version != target_version:
                print(f"Arquivando v{ev.version} (Production → Archived)…")
                client.transition_model_version_stage(
                    name=model_name,
                    version=ev.version,
                    stage="Archived",
                    archive_existing_versions=False,
                )

    # Promover
    print(f"Promovendo {model_name} v{target_version} → {to_stage}…")
    client.transition_model_version_stage(
        name=model_name,
        version=target_version,
        stage=to_stage,
        archive_existing_versions=(to_stage == "Production"),
    )

    # Adicionar tag de promoção
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    client.set_model_version_tag(model_name, target_version, "promoted_at", ts)
    client.set_model_version_tag(model_name, target_version, "promoted_by",
                                 os.getenv("GITHUB_ACTOR", "manual"))

    print(f"✅ {model_name} v{target_version} agora em '{to_stage}'")

    # Sumário para o GitHub Actions (aparece no GITHUB_STEP_SUMMARY)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"## Promoção de Modelo\n\n")
            f.write(f"| Campo | Valor |\n|---|---|\n")
            f.write(f"| Modelo | `{model_name}` |\n")
            f.write(f"| Versão | `{target_version}` |\n")
            f.write(f"| Stage | `{to_stage}` |\n")
            f.write(f"| Timestamp | `{ts}` |\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Promove modelos no MLflow Model Registry.")
    p.add_argument("--model", default=os.getenv("MLFLOW_REGISTERED_MODEL", DEFAULT_MODEL),
                   help="Nome do modelo no registry")
    p.add_argument("--version", help="Versão específica a promover")
    p.add_argument("--from-stage", choices=["None", "Staging", "Production"],
                   help="Promover a versão mais recente deste stage")
    p.add_argument("--to", dest="to_stage", default="Staging",
                   choices=["Staging", "Production", "Archived"],
                   help="Stage destino (default: Staging)")
    p.add_argument("--no-archive", action="store_true",
                   help="Não arquivar versões existentes em Production")
    p.add_argument("--list", action="store_true", help="Listar versões e sair")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    client = get_client()

    if args.list:
        list_versions(client, args.model)
        return

    promote(
        client=client,
        model_name=args.model,
        version=args.version,
        from_stage=args.from_stage,
        to_stage=args.to_stage,
        archive_existing=not args.no_archive,
    )


if __name__ == "__main__":
    main()

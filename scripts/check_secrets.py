#!/usr/bin/env python
"""
Valida secrets e variáveis de ambiente obrigatórias (risco de produção).

Uso:
    python scripts/check_secrets.py
    python scripts/check_secrets.py --environment production
    python scripts/check_secrets.py --environment production --scope etl
    python scripts/check_secrets.py --checklist

Exit codes:
    0 — todos os secrets obrigatórios presentes
    1 — faltam secrets críticos
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

_ALWAYS = ("development", "staging", "production")
_PROD_STAGING = ("staging", "production")


@dataclass(frozen=True)
class SecretSpec:
    name: str
    required_in: tuple[str, ...]
    description: str
    github_secret: str = ""
    scope: str = "optional"  # etl | api | cd | optional


SECRETS: list[SecretSpec] = [
    SecretSpec("DB_PASSWORD", _ALWAYS,
               "Senha PostgreSQL (nunca use 'postgres' em staging/prod)",
               "DB_PASSWORD", "etl"),
    SecretSpec("DB_USER", _ALWAYS, "Usuário PostgreSQL", "DB_USER", "etl"),
    SecretSpec("DB_HOST", _ALWAYS, "Host PostgreSQL", "DB_HOST", "etl"),
    SecretSpec("DB_NAME", _ALWAYS, "Nome do banco", "DB_NAME", "etl"),
    SecretSpec("API_KEY", _PROD_STAGING,
               "Chave X-API-Key da API (fail-closed em staging/prod)",
               "API_KEY / STAGING_API_KEY", "api"),
    SecretSpec("REDIS_PASSWORD", _PROD_STAGING,
               "Senha Redis (--requirepass)",
               "REDIS_PASSWORD / REDIS_PASSWORD_STAGING", "api"),
    SecretSpec("SLACK_WEBHOOK", (),
               "Incoming Webhook Slack (alertas ETL/retrain) — opcional",
               "SLACK_WEBHOOK", "optional"),
    SecretSpec("MLFLOW_TRACKING_URI", (),
               "URI do MLflow Tracking (opcional)",
               "MLFLOW_TRACKING_URI", "optional"),
    SecretSpec("GRAFANA_PASSWORD", (),
               "Senha admin Grafana (perfil monitoring)",
               "—", "optional"),
    SecretSpec("OPENLINEAGE_URL", (),
               "Backend Marquez/OpenLineage (opcional)",
               "—", "optional"),
    SecretSpec("SSH_HOST", (),
               "Host SSH para CD — obrigatório no workflow CD",
               "SSH_HOST", "cd"),
    SecretSpec("SSH_USERNAME", (),
               "Usuário SSH para CD — obrigatório no workflow CD",
               "SSH_USERNAME", "cd"),
    SecretSpec("SSH_PRIVATE_KEY", (),
               "Chave privada SSH para CD — obrigatório no workflow CD",
               "SSH_PRIVATE_KEY", "cd"),
]

_FORBIDDEN_VALUES = {
    "DB_PASSWORD": {"postgres", "password", "changeme", "admin"},
    "API_KEY": {"changeme", "test", "ci-test-api-key"},
    "REDIS_PASSWORD": {"redis", "password"},
    "GRAFANA_PASSWORD": {"admin", "password"},
}


def _env_name(cli_env: str | None) -> str:
    return (cli_env or os.getenv("ENVIRONMENT", "development")).lower().strip()


def check_secrets(
    environment: str,
    scopes: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """
    Retorna (errors, warnings).

    scopes: se informado, avalia apenas esses escopos (ex: {"etl"}).
            Secrets fora do escopo são ignorados.
            Para CD: --scope cd torna SSH_* obrigatórios.
    """
    errors: list[str] = []
    warnings: list[str] = []

    for spec in SECRETS:
        if scopes is not None and spec.scope not in scopes:
            continue

        value = (os.getenv(spec.name) or "").strip()

        required = environment in spec.required_in
        if spec.scope == "cd" and scopes is not None and "cd" in scopes:
            required = True

        if not value:
            msg = f"{spec.name} — {spec.description}"
            if required:
                errors.append(msg)
            else:
                warnings.append(f"(opcional) {msg}")
            continue

        forbidden = _FORBIDDEN_VALUES.get(spec.name, set())
        if value.lower() in {v.lower() for v in forbidden}:
            msg = (
                f"{spec.name} usa valor inseguro/proibido ('{value}') — "
                f"gere com: openssl rand -hex 32"
            )
            if environment in _PROD_STAGING:
                errors.append(msg)
            else:
                warnings.append(msg)

    return errors, warnings


def render_checklist() -> str:
    lines = [
        "# Secrets Checklist — Used Cars ML",
        "",
        "Configure em **GitHub → Settings → Secrets and variables → Actions**.",
        "Localmente: copie `.env.example` → `.env` e preencha.",
        "",
        "| Variável | Scope | GitHub Secret | Obrigatório em | Descrição |",
        "|----------|-------|---------------|----------------|-----------|",
    ]
    for s in SECRETS:
        envs = ", ".join(s.required_in) if s.required_in else (
            "CD workflow" if s.scope == "cd" else "opcional"
        )
        gh = s.github_secret or "—"
        lines.append(
            f"| `{s.name}` | `{s.scope}` | `{gh}` | {envs} | {s.description} |"
        )

    lines += [
        "",
        "## Validação",
        "",
        "```bash",
        "python scripts/check_secrets.py --environment production --scope etl",
        "python scripts/check_secrets.py --environment production --scope api,cd",
        "python scripts/check_secrets.py --checklist",
        "```",
        "",
        "## Geração de senhas",
        "",
        "```bash",
        "openssl rand -hex 32",
        "```",
        "",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Valida secrets de produção.")
    p.add_argument("--environment", "-e", default=None,
                   help="development | staging | production")
    p.add_argument(
        "--scope",
        default=None,
        help="Filtrar por escopo: etl,api,cd (separados por vírgula). "
             "Default: todos.",
    )
    p.add_argument("--checklist", action="store_true",
                   help="Imprime checklist Markdown e sai")
    p.add_argument("--dotenv", type=Path, default=ROOT / ".env",
                   help="Caminho do .env a carregar (default: .env)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.checklist:
        print(render_checklist())
        return 0

    if args.dotenv.exists():
        load_dotenv(args.dotenv)

    environment = _env_name(args.environment)
    scopes = None
    if args.scope:
        scopes = {s.strip() for s in args.scope.split(",") if s.strip()}

    errors, warnings = check_secrets(environment, scopes=scopes)

    scope_label = ",".join(sorted(scopes)) if scopes else "all"
    print(f"Ambiente: {environment}  |  Scope: {scope_label}")
    print(f"Erros: {len(errors)}  |  Avisos: {len(warnings)}")
    print()

    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")

    if errors:
        print("\nFalha: configure os secrets acima antes de deploy.")
        print("Ver: docs/SECRETS.md  |  python scripts/check_secrets.py --checklist")
        return 1

    print("\nOK — secrets obrigatórios presentes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

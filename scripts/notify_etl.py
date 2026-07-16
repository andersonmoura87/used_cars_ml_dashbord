#!/usr/bin/env python
"""
Alertas Slack para o pipeline ETL (UCM-26).

Envia notificações via Incoming Webhook quando:
  - ETL conclui com sucesso
  - ETL falha
  - Validação Great Expectations falha
  - Drift detectado (opcional)

Uso:
    # Sucesso
    python scripts/notify_etl.py --status success --duration 42.5 \\
        --input-rows 10000 --clean-rows 9500

    # Falha
    python scripts/notify_etl.py --status failure --error "GE clean suite failed"

    # A partir de metadados do pipeline
    python scripts/notify_etl.py --from-metadata logs/metadata/pipeline_*.json

    # Dry-run (imprime payload, não envia)
    python scripts/notify_etl.py --status success --dry-run

Variáveis de ambiente:
    SLACK_WEBHOOK — URL do Incoming Webhook (obrigatório para envio real)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent


# ── Payload builders ──────────────────────────────────────────────────────────

def build_slack_payload(
    status: str,
    *,
    duration_seconds: Optional[float] = None,
    input_rows: Optional[int] = None,
    clean_rows: Optional[int] = None,
    removed_rows: Optional[int] = None,
    ge_raw_passed: Optional[bool] = None,
    ge_clean_passed: Optional[bool] = None,
    error: Optional[str] = None,
    drift_detected: Optional[bool] = None,
    drift_score: Optional[float] = None,
    run_url: Optional[str] = None,
    environment: str = "production",
) -> dict[str, Any]:
    """
    Monta o payload Slack Incoming Webhook (attachments + blocks).

    status: "success" | "failure" | "warning"
    """
    status = status.lower()
    icons = {"success": ":white_check_mark:", "failure": ":x:", "warning": ":warning:"}
    colors = {"success": "good", "failure": "danger", "warning": "warning"}
    titles = {
        "success": "ETL Pipeline — Sucesso",
        "failure": "ETL Pipeline — FALHA",
        "warning": "ETL Pipeline — Atenção",
    }

    icon = icons.get(status, ":information_source:")
    color = colors.get(status, "#439FE0")
    title = titles.get(status, f"ETL Pipeline — {status}")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    fields = [
        {"title": "Ambiente", "value": environment, "short": True},
        {"title": "Horário", "value": ts, "short": True},
    ]
    if duration_seconds is not None:
        fields.append({
            "title": "Duração",
            "value": f"{duration_seconds:.1f}s",
            "short": True,
        })
    if input_rows is not None:
        fields.append({"title": "Linhas input", "value": f"{input_rows:,}", "short": True})
    if clean_rows is not None:
        fields.append({"title": "Linhas limpas", "value": f"{clean_rows:,}", "short": True})
    if removed_rows is not None:
        fields.append({"title": "Removidas", "value": f"{removed_rows:,}", "short": True})
    if ge_raw_passed is not None:
        fields.append({
            "title": "GE raw",
            "value": "pass" if ge_raw_passed else "FAIL",
            "short": True,
        })
    if ge_clean_passed is not None:
        fields.append({
            "title": "GE clean",
            "value": "pass" if ge_clean_passed else "FAIL",
            "short": True,
        })
    if drift_detected is not None:
        fields.append({
            "title": "Drift",
            "value": (
                f"DETECTADO (score={drift_score:.3f})" if drift_detected
                else "ok"
            ) if drift_score is not None else ("DETECTADO" if drift_detected else "ok"),
            "short": True,
        })

    text_parts = [f"{icon} *{title}*"]
    if error:
        text_parts.append(f"\n```{error[:500]}```")
    if run_url:
        text_parts.append(f"\n<{run_url}|Ver run no GitHub Actions>")

    return {
        "text": " ".join(text_parts[:1]),
        "attachments": [
            {
                "color": color,
                "text": "\n".join(text_parts),
                "fields": fields,
                "footer": "used-cars-ml · UCM-26",
                "ts": int(datetime.now(timezone.utc).timestamp()),
            }
        ],
    }


def send_slack(payload: dict[str, Any], webhook_url: str, timeout: int = 15) -> bool:
    """
    Envia payload para o Slack Incoming Webhook.

    Returns:
        True se HTTP 200, False caso contrário.
    """
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            ok = 200 <= resp.status < 300
            if not ok:
                logger.error("Slack respondeu HTTP %s", resp.status)
            return ok
    except HTTPError as exc:
        logger.error("Slack HTTPError %s: %s", exc.code, exc.read().decode(errors="replace")[:200])
        return False
    except URLError as exc:
        logger.error("Slack URLError: %s", exc.reason)
        return False


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_from_metadata(path: Path) -> dict[str, Any]:
    """Extrai campos de notificação a partir de um JSON de metadados do pipeline."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    ge_raw = raw.get("ge_raw_passed")
    ge_clean = raw.get("ge_clean_passed")
    status = "success"
    if ge_raw is False or ge_clean is False:
        status = "warning"
    return {
        "status": status,
        "duration_seconds": raw.get("duration_seconds"),
        "input_rows": raw.get("total_input_records"),
        "clean_rows": raw.get("total_clean_records"),
        "removed_rows": raw.get("total_removed_records"),
        "ge_raw_passed": ge_raw,
        "ge_clean_passed": ge_clean,
    }


def find_latest_pipeline_metadata(metadata_dir: Path | None = None) -> Optional[Path]:
    """Encontra o pipeline_*.json mais recente em logs/metadata/."""
    metadata_dir = metadata_dir or (ROOT / "logs" / "metadata")
    if not metadata_dir.is_dir():
        return None
    files = sorted(metadata_dir.glob("pipeline_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Alertas Slack para ETL (UCM-26).")
    p.add_argument("--status", choices=["success", "failure", "warning"],
                   help="Status do pipeline")
    p.add_argument("--from-metadata", type=Path, help="JSON de metadados do pipeline")
    p.add_argument("--duration", type=float, dest="duration_seconds")
    p.add_argument("--input-rows", type=int)
    p.add_argument("--clean-rows", type=int)
    p.add_argument("--removed-rows", type=int)
    p.add_argument("--ge-raw", choices=["pass", "fail"], default=None)
    p.add_argument("--ge-clean", choices=["pass", "fail"], default=None)
    p.add_argument("--error", default=None)
    p.add_argument("--drift-detected", action="store_true")
    p.add_argument("--drift-score", type=float, default=None)
    p.add_argument("--run-url", default=os.getenv("GITHUB_RUN_URL", ""))
    p.add_argument("--environment", default=os.getenv("ENVIRONMENT", "production"))
    p.add_argument("--webhook", default=os.getenv("SLACK_WEBHOOK", ""))
    p.add_argument("--dry-run", action="store_true", help="Imprime payload sem enviar")
    return p.parse_args(argv)


def _bool_from_pass_fail(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    return value == "pass"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)

    kwargs: dict[str, Any] = {
        "duration_seconds": args.duration_seconds,
        "input_rows": args.input_rows,
        "clean_rows": args.clean_rows,
        "removed_rows": args.removed_rows,
        "ge_raw_passed": _bool_from_pass_fail(args.ge_raw),
        "ge_clean_passed": _bool_from_pass_fail(args.ge_clean),
        "error": args.error,
        "drift_detected": args.drift_detected if args.drift_detected else None,
        "drift_score": args.drift_score,
        "run_url": args.run_url or None,
        "environment": args.environment,
    }

    status = args.status
    if args.from_metadata:
        meta = load_from_metadata(args.from_metadata)
        status = status or meta.pop("status")
        for k, v in meta.items():
            if kwargs.get(k) is None:
                kwargs[k] = v
    elif status is None:
        latest = find_latest_pipeline_metadata()
        if latest:
            logger.info("Usando metadados: %s", latest)
            meta = load_from_metadata(latest)
            status = meta.pop("status")
            kwargs.update({k: v for k, v in meta.items() if kwargs.get(k) is None})
        else:
            logger.error("Informe --status ou --from-metadata")
            return 1

    assert status is not None
    # Se GE falhou e status era success → elevar para warning
    if status == "success" and (
        kwargs.get("ge_raw_passed") is False or kwargs.get("ge_clean_passed") is False
    ):
        status = "warning"

    payload = build_slack_payload(status, **kwargs)

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    webhook = args.webhook
    if not webhook:
        logger.warning("SLACK_WEBHOOK não configurado — notificação pulada (no-op)")
        # Escreve no Step Summary se disponível
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write(f"\n## Slack notify (skipped)\nStatus: `{status}` — webhook ausente\n")
        return 0

    ok = send_slack(payload, webhook)
    if ok:
        logger.info("Notificação Slack enviada (status=%s)", status)
        return 0
    logger.error("Falha ao enviar notificação Slack")
    return 1


if __name__ == "__main__":
    sys.exit(main())

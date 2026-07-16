#!/usr/bin/env python
"""
Dashboard de tendência de qualidade de dados (UCM-26).

Agrega histórico de validações Great Expectations e metadados de pipeline
em um relatório de tendência:

  data/quality/quality_trend.json   — dados estruturados (séries temporais)
  docs/quality/QUALITY_TREND.md     — relatório Markdown legível

Fontes:
  - data/quality/quality_history.jsonl   (append-only, gerado por ge_validation)
  - data/quality/ge_summary_*.json       (fallback se history estiver vazio)
  - logs/metadata/pipeline_*.json        (volume de linhas / duração)

Uso:
    python scripts/quality_trend.py
    python scripts/quality_trend.py --days 30 --stdout
    python scripts/quality_trend.py --history data/quality/quality_history.jsonl

No CI: grava artefato + escreve no GITHUB_STEP_SUMMARY.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY = ROOT / "data" / "quality" / "quality_history.jsonl"
DEFAULT_QUALITY_DIR = ROOT / "data" / "quality"
DEFAULT_TREND_JSON = ROOT / "data" / "quality" / "quality_trend.json"
DEFAULT_TREND_MD = ROOT / "docs" / "quality" / "QUALITY_TREND.md"


# ── Loaders ───────────────────────────────────────────────────────────────────

def _parse_ts(value: str) -> Optional[datetime]:
    """Parse timestamps flexíveis (ISO ou YYYYMMDD_HHMMSS)."""
    if not value:
        return None
    value = value.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y%m%d_%H%M%S",
    ):
        try:
            dt = datetime.strptime(value.replace("Z", "+00:00") if "Z" in value else value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def load_history(history_path: Path) -> list[dict[str, Any]]:
    """Carrega quality_history.jsonl (uma entrada por linha)."""
    if not history_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def load_ge_summaries(quality_dir: Path) -> list[dict[str, Any]]:
    """Fallback: carrega ge_summary_*.json individuais."""
    entries: list[dict[str, Any]] = []
    for path in sorted(quality_dir.glob("ge_summary_*.json")):
        try:
            entries.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return entries


def load_pipeline_stats(metadata_dir: Path) -> list[dict[str, Any]]:
    """Carrega métricas de volume dos runs de pipeline."""
    if not metadata_dir.is_dir():
        return []
    stats: list[dict[str, Any]] = []
    for path in sorted(metadata_dir.glob("pipeline_*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        stats.append({
            "timestamp": raw.get("pipeline_end") or raw.get("pipeline_start") or path.stem,
            "duration_seconds": raw.get("duration_seconds"),
            "input_rows": raw.get("total_input_records"),
            "clean_rows": raw.get("total_clean_records"),
            "removed_rows": raw.get("total_removed_records"),
            "ge_raw_passed": raw.get("ge_raw_passed"),
            "ge_clean_passed": raw.get("ge_clean_passed"),
        })
    return stats


# ── Agregação ─────────────────────────────────────────────────────────────────

def filter_by_days(entries: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    if days <= 0:
        return entries
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered = []
    for e in entries:
        dt = _parse_ts(str(e.get("evaluated_at") or e.get("timestamp") or ""))
        if dt is None or dt >= cutoff:
            filtered.append(e)
    return filtered


def build_trend(
    ge_entries: list[dict[str, Any]],
    pipeline_stats: list[dict[str, Any]],
    days: int = 30,
) -> dict[str, Any]:
    """
    Agrega tendência de qualidade.

    Returns:
        Dict com series por suite, overview e pipeline_volume.
    """
    ge_entries = filter_by_days(ge_entries, days)

    by_suite: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in ge_entries:
        suite = e.get("suite", "unknown")
        by_suite[suite].append({
            "timestamp": e.get("evaluated_at") or e.get("timestamp"),
            "pass_rate": float(e.get("pass_rate", 0)),
            "success": bool(e.get("success", False)),
            "evaluated": int(e.get("evaluated", 0) or 0),
            "failed": int(e.get("failed", 0) or 0),
        })

    suite_summaries = {}
    for suite, points in by_suite.items():
        rates = [p["pass_rate"] for p in points]
        successes = sum(1 for p in points if p["success"])
        suite_summaries[suite] = {
            "runs": len(points),
            "success_count": successes,
            "success_rate": round(successes / len(points), 4) if points else 0.0,
            "avg_pass_rate": round(sum(rates) / len(rates), 4) if rates else 0.0,
            "min_pass_rate": round(min(rates), 4) if rates else 0.0,
            "max_pass_rate": round(max(rates), 4) if rates else 0.0,
            "latest_pass_rate": rates[-1] if rates else 0.0,
            "latest_success": points[-1]["success"] if points else False,
            "series": points,
        }

    # Tendência: comparar primeira metade vs segunda metade (por suite)
    alerts: list[str] = []
    for suite, summary in suite_summaries.items():
        series = summary["series"]
        if len(series) >= 4:
            mid = len(series) // 2
            first_avg = sum(p["pass_rate"] for p in series[:mid]) / mid
            second_avg = sum(p["pass_rate"] for p in series[mid:]) / (len(series) - mid)
            delta = second_avg - first_avg
            summary["trend_delta"] = round(delta, 4)
            if delta < -0.05:
                alerts.append(
                    f"Degradação em `{suite}`: pass_rate caiu {abs(delta):.1%} "
                    f"({first_avg:.1%} → {second_avg:.1%})"
                )
            elif delta > 0.05:
                alerts.append(
                    f"Melhoria em `{suite}`: pass_rate subiu {delta:.1%} "
                    f"({first_avg:.1%} → {second_avg:.1%})"
                )
        else:
            summary["trend_delta"] = 0.0

        if summary["latest_pass_rate"] < 0.9:
            alerts.append(
                f"`{suite}` pass_rate atual baixo: {summary['latest_pass_rate']:.1%}"
            )

    overall_rates = [
        p["pass_rate"]
        for points in by_suite.values()
        for p in points
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "total_ge_runs": len(ge_entries),
        "overview": {
            "avg_pass_rate": round(sum(overall_rates) / len(overall_rates), 4) if overall_rates else None,
            "suites": list(suite_summaries.keys()),
            "alert_count": len(alerts),
        },
        "suites": suite_summaries,
        "pipeline_volume": pipeline_stats[-20:],  # últimos 20
        "alerts": alerts,
        "status": "degraded" if alerts else ("healthy" if ge_entries else "no_data"),
    }


def render_markdown(trend: dict[str, Any]) -> str:
    """Renderiza relatório Markdown da tendência de qualidade."""
    generated = trend.get("generated_at", "")
    status = trend.get("status", "unknown")
    icon = {"": "", "healthy": ":white_check_mark:", "degraded": ":warning:", "no_data": ":grey_question:"}.get(status, "")

    lines = [
        f"# Data Quality Trend",
        "",
        f"> Gerado em `{generated}` · janela: {trend.get('window_days')} dias · UCM-26",
        "",
        f"**Status:** {icon} `{status}`  ",
        f"**Runs GE no período:** {trend.get('total_ge_runs', 0)}  ",
        f"**Pass rate médio:** {trend.get('overview', {}).get('avg_pass_rate') or 'N/A'}",
        "",
        "---",
        "",
        "## Suites",
        "",
        "| Suite | Runs | Success rate | Avg pass rate | Min | Latest | Trend Δ |",
        "|-------|------|--------------|---------------|-----|--------|---------|",
    ]

    for suite, s in sorted(trend.get("suites", {}).items()):
        delta = s.get("trend_delta", 0)
        delta_s = f"{delta:+.1%}" if delta else "—"
        lines.append(
            f"| `{suite}` | {s['runs']} | {s['success_rate']:.1%} | "
            f"{s['avg_pass_rate']:.1%} | {s['min_pass_rate']:.1%} | "
            f"{s['latest_pass_rate']:.1%} | {delta_s} |"
        )

    alerts = trend.get("alerts") or []
    lines += ["", "## Alerts", ""]
    if alerts:
        for a in alerts:
            lines.append(f"- :warning: {a}")
    else:
        lines.append("- Nenhum alerta no período.")

    volume = trend.get("pipeline_volume") or []
    if volume:
        lines += [
            "",
            "## Pipeline Volume (últimos runs)",
            "",
            "| Timestamp | Input | Clean | Removed | Duração |",
            "|-----------|-------|-------|---------|---------|",
        ]
        for v in volume[-10:]:
            dur = v.get("duration_seconds")
            dur_s = f"{dur:.1f}s" if isinstance(dur, (int, float)) else "N/A"
            lines.append(
                f"| {v.get('timestamp', 'N/A')} | "
                f"{v.get('input_rows', 'N/A')} | "
                f"{v.get('clean_rows', 'N/A')} | "
                f"{v.get('removed_rows', 'N/A')} | "
                f"{dur_s} |"
            )

    lines += [
        "",
        "---",
        "",
        "*Gerado por `scripts/quality_trend.py`. Fonte: `data/quality/quality_history.jsonl`.*",
        "",
    ]
    return "\n".join(lines)


# ── Persistência ──────────────────────────────────────────────────────────────

def write_outputs(trend: dict[str, Any], json_path: Path, md_path: Path) -> list[Path]:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(trend, indent=2, default=str), encoding="utf-8")
    md = render_markdown(trend)
    md_path.write_text(md, encoding="utf-8")
    return [json_path, md_path]


def _write_github_summary(trend: dict[str, Any], md: str) -> None:
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n" + md + "\n")

    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"quality_status={trend.get('status', 'unknown')}\n")
            f.write(f"alert_count={trend.get('overview', {}).get('alert_count', 0)}\n")
            avg = trend.get("overview", {}).get("avg_pass_rate")
            if avg is not None:
                f.write(f"avg_pass_rate={avg}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Tendência de qualidade de dados (UCM-26).")
    p.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    p.add_argument("--quality-dir", type=Path, default=DEFAULT_QUALITY_DIR)
    p.add_argument("--metadata-dir", type=Path, default=ROOT / "logs" / "metadata")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--output-json", type=Path, default=DEFAULT_TREND_JSON)
    p.add_argument("--output-md", type=Path, default=DEFAULT_TREND_MD)
    p.add_argument("--stdout", action="store_true")
    p.add_argument("--fail-on-degraded", action="store_true",
                   help="Exit 1 se status=degraded (útil no CI)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)

    ge_entries = load_history(args.history)
    if not ge_entries:
        logger.info("History vazio — tentando ge_summary_*.json")
        ge_entries = load_ge_summaries(args.quality_dir)

    pipeline_stats = load_pipeline_stats(args.metadata_dir)
    trend = build_trend(ge_entries, pipeline_stats, days=args.days)
    md = render_markdown(trend)

    if args.stdout:
        print(md)
    else:
        paths = write_outputs(trend, args.output_json, args.output_md)
        for path in paths:
            logger.info("Escrito: %s", path)
        print(f"OK — quality trend: status={trend['status']} alerts={len(trend['alerts'])}")

    _write_github_summary(trend, md)

    if args.fail_on_degraded and trend["status"] == "degraded":
        logger.warning("Quality degradada — falhando (--fail-on-degraded)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

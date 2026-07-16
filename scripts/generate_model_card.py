#!/usr/bin/env python
"""
Gera Model Cards automáticos para o modelo de preços (UCM-25).

Fontes de dados (em ordem de prioridade):
  1. --meta PATH          — JSON de metadados local (gerado por AdvancedPriceModel.save)
  2. MLflow Registry      — se MLFLOW_TRACKING_URI estiver configurado
  3. --metrics / defaults — valores passados via CLI ou placeholders

Saída:
  docs/model_cards/MODEL_CARD.md              — card "latest" (sempre sobrescrito)
  docs/model_cards/MODEL_CARD_v{N}_{ts}.md    — versão imutável (quando --versioned)

Uso:
    # A partir de metadados locais
    python scripts/generate_model_card.py --meta models/price_model_20260101_meta.json

    # A partir do MLflow (Production)
    python scripts/generate_model_card.py --stage Production

    # Dry-run: imprime no stdout sem gravar
    python scripts/generate_model_card.py --meta models/..._meta.json --stdout

Variáveis de ambiente:
    MLFLOW_TRACKING_URI     — URI do servidor MLflow (opcional)
    MLFLOW_REGISTERED_MODEL — nome do modelo (default: used_cars_price_model)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "model_cards"
DEFAULT_MODEL_NAME = "used_cars_price_model"


# ── Estrutura de dados do card ────────────────────────────────────────────────

@dataclass
class ModelCardData:
    """Dados necessários para renderizar um Model Card."""

    model_name: str = DEFAULT_MODEL_NAME
    version: str = "unknown"
    stage: str = "None"
    created_at: str = ""
    git_sha: str = "unknown"
    run_id: str = ""

    # Intenção / escopo
    intended_use: str = (
        "Estimar o preço justo de veículos usados com base em atributos "
        "do anúncio (ano, fabricante, odômetro, combustível, etc.). "
        "Destinado a compradores, vendedores e gestores de marketplace."
    )
    out_of_scope: str = (
        "Não deve ser usado para veículos comerciais pesados, leilões, "
        "avaliação de sinistros/seguro, ou mercados fora do dataset de treino."
    )

    # Features
    categorical_features: list[str] = field(default_factory=list)
    numerical_features: list[str] = field(default_factory=list)
    target: str = "price"

    # Métricas
    r2: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None
    extra_metrics: dict[str, float] = field(default_factory=dict)

    # Treino
    training_rows: Optional[int] = None
    data_hash: str = ""
    model_type: str = "XGBoost Regressor"
    model_params: dict[str, Any] = field(default_factory=dict)
    validation_method: str = "TimeSeriesSplit (5-fold)"

    # Ética / limitações
    limitations: list[str] = field(default_factory=lambda: [
        "Performance degrada em regiões/marcas pouco representadas no treino.",
        "Preços de anúncios podem divergir do valor de transação real.",
        "Drift de mercado (inflação, sazonalidade) exige retreinamento periódico.",
        "Não captura danos ocultos, histórico de acidentes ou documentação irregular.",
    ])
    ethical_considerations: list[str] = field(default_factory=lambda: [
        "O modelo não usa atributos sensíveis (raça, gênero, religião).",
        "Viés geográfico: estados com mais anúncios dominam as estimativas.",
        "Preços preditos não devem ser usados como única fonte para decisões "
        "financeiras de alto impacto sem revisão humana.",
    ])

    # Auditoria
    promoted_by: str = ""
    promotion_reason: str = ""
    contact: str = "https://github.com/andersonmoura87/used_cars_ml_dashbord"


def _fmt_metric(value: Optional[float], decimals: int = 4) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}"


def render_model_card(data: ModelCardData) -> str:
    """
    Renderiza um Model Card em Markdown (formato compatível com
    Google Model Cards / Hugging Face Model Card).
    """
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    created = data.created_at or generated_at

    cat_feats = ", ".join(f"`{f}`" for f in data.categorical_features) or "_não informado_"
    num_feats = ", ".join(f"`{f}`" for f in data.numerical_features) or "_não informado_"

    params_block = "```json\n" + json.dumps(data.model_params or {}, indent=2, default=str) + "\n```"
    if not data.model_params:
        params_block = "_não informado_"

    extra_rows = ""
    for k, v in sorted(data.extra_metrics.items()):
        extra_rows += f"| `{k}` | {_fmt_metric(v)} |\n"

    limitations = "\n".join(f"- {item}" for item in data.limitations)
    ethics = "\n".join(f"- {item}" for item in data.ethical_considerations)

    audit_section = ""
    if data.promoted_by or data.promotion_reason:
        audit_section = f"""
## Audit Trail

| Campo | Valor |
|-------|-------|
| Promovido por | @{data.promoted_by or "N/A"} |
| Motivo | {data.promotion_reason or "N/A"} |
| Stage atual | `{data.stage}` |
"""

    return f"""# Model Card: {data.model_name}

> Gerado automaticamente em `{generated_at}` · UCM-25

| Campo | Valor |
|-------|-------|
| **Versão** | `{data.version}` |
| **Stage** | `{data.stage}` |
| **Criado em** | {created} |
| **Git SHA** | `{data.git_sha}` |
| **MLflow Run** | `{data.run_id or "N/A"}` |
| **Tipo** | {data.model_type} |
| **Contato** | {data.contact} |

---

## Model Details

Modelo de regressão baseado em **XGBoost** para prever o preço de veículos
usados a partir de atributos do anúncio.

### Hyperparameters

{params_block}

### Validação

{data.validation_method}

---

## Intended Use

{data.intended_use}

### Out of Scope

{data.out_of_scope}

---

## Training Data

| Campo | Valor |
|-------|-------|
| Linhas de treino | {data.training_rows if data.training_rows is not None else "N/A"} |
| Data hash (SHA-256) | `{data.data_hash or "N/A"}` |
| Target | `{data.target}` |

### Features categóricas

{cat_feats}

### Features numéricas

{num_feats}

---

## Evaluation Metrics

| Métrica | Valor |
|---------|-------|
| R² | {_fmt_metric(data.r2)} |
| RMSE | {_fmt_metric(data.rmse, 2)} |
| MAE | {_fmt_metric(data.mae, 2)} |
{extra_rows}
> Maior R² e menor RMSE/MAE indicam melhor desempenho. Comparação champion/challenger
> usa margem mínima configurável (`--min-improvement`).

---

## Limitations

{limitations}

---

## Ethical Considerations

{ethics}
{audit_section}
---

## How to Cite

```
{data.model_name} v{data.version} ({created}).
Used Cars ML Dashboard — {data.contact}
```

*Este card é gerado por `scripts/generate_model_card.py` e não deve ser editado manualmente.*
"""


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_from_meta(meta_path: Path) -> ModelCardData:
    """Carrega ModelCardData a partir de um JSON de metadados local."""
    raw = json.loads(meta_path.read_text(encoding="utf-8"))
    metrics = raw.get("metrics") or {}

    known = {"r2", "rmse", "mae"}
    extra = {k: float(v) for k, v in metrics.items() if k not in known and isinstance(v, (int, float))}

    return ModelCardData(
        model_name=raw.get("model_name", DEFAULT_MODEL_NAME),
        version=str(raw.get("version", meta_path.stem)),
        stage=raw.get("stage", "None"),
        created_at=str(raw.get("saved_at", "")),
        git_sha=raw.get("git_sha", os.getenv("GIT_SHA", "unknown")),
        categorical_features=list(raw.get("categorical_features") or []),
        numerical_features=list(raw.get("numerical_features") or []),
        target=raw.get("target", "price"),
        r2=metrics.get("r2"),
        rmse=metrics.get("rmse"),
        mae=metrics.get("mae"),
        extra_metrics=extra,
        training_rows=raw.get("training_rows"),
        data_hash=raw.get("data_hash") or "",
        model_params=dict(raw.get("model_params") or {}),
        validation_method=raw.get("validation_method", "TimeSeriesSplit (5-fold)"),
    )


def load_from_mlflow(
    stage: str = "Production",
    version: Optional[str] = None,
    model_name: Optional[str] = None,
) -> ModelCardData:
    """Carrega ModelCardData a partir do MLflow Model Registry."""
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
    except ImportError as exc:
        raise RuntimeError("mlflow não instalado — use --meta ou pip install mlflow") from exc

    uri = os.getenv("MLFLOW_TRACKING_URI")
    if not uri:
        raise RuntimeError("MLFLOW_TRACKING_URI não definido")

    mlflow.set_tracking_uri(uri)
    client = MlflowClient()
    name = model_name or os.getenv("MLFLOW_REGISTERED_MODEL", DEFAULT_MODEL_NAME)

    if version:
        mv = client.get_model_version(name, version)
    else:
        versions = client.get_latest_versions(name, stages=[stage])
        if not versions:
            raise RuntimeError(f"Nenhuma versão em stage '{stage}' para modelo '{name}'")
        mv = versions[0]

    run = client.get_run(mv.run_id)
    metrics = dict(run.data.metrics)
    params = dict(run.data.params)
    tags = dict(run.data.tags)

    cat = []
    num = []
    if "categorical_features" in params:
        cat = [f.strip() for f in params["categorical_features"].split(",") if f.strip()]
    if "numerical_features" in params:
        num = [f.strip() for f in params["numerical_features"].split(",") if f.strip()]

    known = {"r2", "rmse", "mae"}
    extra = {k: float(v) for k, v in metrics.items() if k not in known}

    created = datetime.fromtimestamp(
        mv.creation_timestamp / 1000, tz=timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")

    return ModelCardData(
        model_name=name,
        version=str(mv.version),
        stage=mv.current_stage,
        created_at=created,
        git_sha=tags.get("git_sha", os.getenv("GIT_SHA", "unknown")),
        run_id=mv.run_id,
        categorical_features=cat,
        numerical_features=num,
        target=params.get("target", "price"),
        r2=metrics.get("r2"),
        rmse=metrics.get("rmse"),
        mae=metrics.get("mae"),
        extra_metrics=extra,
        training_rows=int(tags["n_records"]) if tags.get("n_records", "").isdigit() else None,
        data_hash=tags.get("data_hash", ""),
        model_params={k: v for k, v in params.items()
                      if k not in ("categorical_features", "numerical_features", "target")},
        validation_method=tags.get("validation_method", "TimeSeriesSplit (5-fold)"),
    )


def find_latest_meta(models_dir: Path | None = None) -> Optional[Path]:
    """Encontra o arquivo *_meta.json mais recente em models/."""
    models_dir = models_dir or (ROOT / "models")
    if not models_dir.is_dir():
        return None
    metas = sorted(models_dir.glob("*_meta.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return metas[0] if metas else None


# ── Persistência ──────────────────────────────────────────────────────────────

def write_model_card(
    markdown: str,
    output_dir: Path,
    version: str,
    versioned: bool = True,
) -> list[Path]:
    """
    Grava MODEL_CARD.md (latest) e opcionalmente uma cópia versionada.

    Returns:
        Lista de paths gravados.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    latest = output_dir / "MODEL_CARD.md"
    latest.write_text(markdown, encoding="utf-8")
    written.append(latest)

    if versioned:
        safe_version = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(version))
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        versioned_path = output_dir / f"MODEL_CARD_v{safe_version}_{ts}.md"
        versioned_path.write_text(markdown, encoding="utf-8")
        written.append(versioned_path)

    return written


def _write_github_outputs(paths: list[Path], data: ModelCardData) -> None:
    """Escreve outputs para GitHub Actions se GITHUB_OUTPUT estiver definido."""
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"card_path={paths[0]}\n")
            f.write(f"model_version={data.version}\n")
            f.write(f"model_stage={data.stage}\n")
            if data.r2 is not None:
                f.write(f"r2={data.r2}\n")

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## :page_facing_up: Model Card gerado\n\n")
            f.write(f"| Campo | Valor |\n|-------|-------|\n")
            f.write(f"| Modelo | `{data.model_name}` |\n")
            f.write(f"| Versão | `{data.version}` |\n")
            f.write(f"| Stage | `{data.stage}` |\n")
            f.write(f"| R² | {_fmt_metric(data.r2)} |\n")
            f.write(f"| RMSE | {_fmt_metric(data.rmse, 2)} |\n")
            f.write(f"| Artefato | `{paths[0].name}` |\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gera Model Card automático (UCM-25).")
    p.add_argument("--meta", type=Path, help="Caminho para *_meta.json local")
    p.add_argument("--stage", default="Production",
                   help="Stage MLflow a consultar (default: Production)")
    p.add_argument("--version", help="Versão específica do modelo no MLflow")
    p.add_argument("--model-name", default=None, help="Nome do modelo registrado")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--versioned", action="store_true", default=True,
                   help="Também gravar cópia versionada (default: True)")
    p.add_argument("--no-versioned", action="store_false", dest="versioned")
    p.add_argument("--stdout", action="store_true", help="Imprimir no stdout sem gravar")
    p.add_argument("--promoted-by", default=os.getenv("GITHUB_ACTOR", ""))
    p.add_argument("--promotion-reason", default="")
    p.add_argument("--git-sha", default=os.getenv("GIT_SHA", "unknown"))
    p.add_argument("--json-dump", type=Path, help="Também salvar dados brutos em JSON")
    return p.parse_args(argv)


def build_card_data(args: argparse.Namespace) -> ModelCardData:
    """Resolve a fonte de dados e retorna ModelCardData."""
    if args.meta:
        if not args.meta.exists():
            raise FileNotFoundError(f"Meta não encontrado: {args.meta}")
        data = load_from_meta(args.meta)
    elif os.getenv("MLFLOW_TRACKING_URI"):
        try:
            data = load_from_mlflow(
                stage=args.stage,
                version=args.version,
                model_name=args.model_name,
            )
        except Exception as exc:
            logger.warning("MLflow indisponível (%s) — tentando meta local", exc)
            meta = find_latest_meta()
            if meta is None:
                raise
            data = load_from_meta(meta)
    else:
        meta = find_latest_meta()
        if meta is None:
            raise RuntimeError(
                "Nenhuma fonte de dados: passe --meta, configure MLFLOW_TRACKING_URI "
                "ou salve um *_meta.json em models/"
            )
        logger.info("Usando meta local: %s", meta)
        data = load_from_meta(meta)

    if args.git_sha and args.git_sha != "unknown":
        data.git_sha = args.git_sha
    if args.promoted_by:
        data.promoted_by = args.promoted_by
    if args.promotion_reason:
        data.promotion_reason = args.promotion_reason
    if args.model_name:
        data.model_name = args.model_name

    return data


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)

    try:
        data = build_card_data(args)
    except Exception as exc:
        logger.error("Falha ao coletar dados do Model Card: %s", exc)
        return 1

    markdown = render_model_card(data)

    if args.stdout:
        print(markdown)
        return 0

    paths = write_model_card(
        markdown=markdown,
        output_dir=args.output_dir,
        version=data.version,
        versioned=args.versioned,
    )
    for path in paths:
        logger.info("Model Card gravado: %s", path)

    if args.json_dump:
        args.json_dump.parent.mkdir(parents=True, exist_ok=True)
        args.json_dump.write_text(
            json.dumps(asdict(data), indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("JSON dump: %s", args.json_dump)

    _write_github_outputs(paths, data)
    print(f"OK — Model Card gerado: {paths[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

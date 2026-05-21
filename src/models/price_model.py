from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import shap
import statsmodels.api as sm
import xgboost as xgb
from scipy import stats
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit, cross_validate
from sklearn.preprocessing import LabelEncoder, RobustScaler

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).parent.parent.parent / "models"

# ── MLflow — importação opcional ──────────────────────────────────────────────
try:
    import mlflow
    import mlflow.xgboost
    from mlflow.models import infer_signature

    _MLFLOW_AVAILABLE = True
except ImportError:  # pragma: no cover
    _MLFLOW_AVAILABLE = False


def _mlflow_active() -> bool:
    """Retorna True se MLflow estiver disponível e MLFLOW_TRACKING_URI configurado."""
    return _MLFLOW_AVAILABLE and bool(os.getenv("MLFLOW_TRACKING_URI"))

class AdvancedPriceModel:
    """Classe para modelagem avançada de preços de veículos."""
    
    def __init__(
        self,
        categorical_features: List[str],
        numerical_features: List[str],
        target: str = 'price'
    ):
        self.categorical_features = categorical_features
        self.numerical_features = numerical_features
        self.target = target
        
        # Preprocessadores
        self.label_encoders = {
            col: LabelEncoder() for col in categorical_features
        }
        self.scaler = RobustScaler()
        
        # Modelo
        self.model = xgb.XGBRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=6,
            min_child_weight=1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )
        
        self.feature_names: List[str] | None = None
        self._active_run_id: str | None = None  # preenchido após train() com MLflow
        
    def prepare_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        """
        Prepara features para o modelo.

        Args:
            df:  DataFrame de entrada.
            fit: Se True, re-fita encoders e scaler (somente no treino).
                 Se False (padrão), apenas transforma — correto para inferência.
        """
        X = pd.DataFrame()

        for col in self.categorical_features:
            if col in df.columns:
                if fit:
                    X[col] = self.label_encoders[col].fit_transform(df[col].fillna('missing'))
                else:
                    X[col] = self.label_encoders[col].transform(df[col].fillna('missing'))

        if self.numerical_features:
            numeric_data = df[self.numerical_features].fillna(df[self.numerical_features].median())
            if fit:
                X[self.numerical_features] = self.scaler.fit_transform(numeric_data)
            else:
                X[self.numerical_features] = self.scaler.transform(numeric_data)

        self.feature_names = X.columns.tolist()
        return X
    
    def train(
        self,
        df: pd.DataFrame,
        validation_method: str = "time_series",
        mlflow_experiment: str = "used_cars_price_model",
        mlflow_run_name: str | None = None,
        mlflow_tags: Dict[str, str] | None = None,
    ) -> Dict[str, float]:
        """
        Treina o modelo com validação robusta e opcionalmente loga no MLflow.

        Args:
            df:                 Dataset de treino.
            validation_method:  'time_series' (TimeSeriesSplit 5-fold) ou 'full'.
            mlflow_experiment:  Nome do experimento MLflow (criado se não existir).
            mlflow_run_name:    Nome descritivo do run (auto-gerado se None).
            mlflow_tags:        Tags adicionais para o run.
        """
        X = self.prepare_features(df, fit=True)
        y = df[self.target]

        if validation_method == "time_series":
            tscv = TimeSeriesSplit(n_splits=5)
            cv_results = cross_validate(
                self.model, X, y,
                cv=tscv,
                scoring=["r2", "neg_mean_squared_error", "neg_mean_absolute_error"],
                return_train_score=False,
            )
            metrics = {
                "r2":   float(np.mean(cv_results["test_r2"])),
                "rmse": float(np.sqrt(-np.mean(cv_results["test_neg_mean_squared_error"]))),
                "mae":  float(-np.mean(cv_results["test_neg_mean_absolute_error"])),
            }
            self.model.fit(X, y)
        else:
            self.model.fit(X, y)
            y_pred = self.model.predict(X)
            metrics = {
                "r2":   float(self.model.score(X, y)),
                "rmse": float(np.sqrt(np.mean((y - y_pred) ** 2))),
                "mae":  float(np.mean(np.abs(y - y_pred))),
            }

        # ── MLflow logging (opcional) ────────────────────────────────────────
        if _mlflow_active():
            self._log_to_mlflow(
                X=X, y=y,
                metrics=metrics,
                experiment_name=mlflow_experiment,
                run_name=mlflow_run_name or f"train_{datetime.now():%Y%m%d_%H%M%S}",
                tags={
                    "validation_method": validation_method,
                    "n_records": str(len(df)),
                    "features": ",".join(self.feature_names or []),
                    **(mlflow_tags or {}),
                },
            )

        return metrics

    def _log_to_mlflow(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        metrics: Dict[str, float],
        experiment_name: str,
        run_name: str,
        tags: Dict[str, str],
    ) -> None:
        """Loga parâmetros, métricas e artefatos no MLflow."""
        mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
        mlflow.set_experiment(experiment_name)

        with mlflow.start_run(run_name=run_name, tags=tags) as run:
            self._active_run_id = run.info.run_id

            # parâmetros do modelo
            mlflow.log_params(self.model.get_params())
            mlflow.log_params({
                "categorical_features": ",".join(self.categorical_features),
                "numerical_features": ",".join(self.numerical_features),
                "target": self.target,
            })

            # métricas de validação
            mlflow.log_metrics(metrics)

            # artefato: modelo XGBoost nativo
            signature = infer_signature(X, y)
            mlflow.xgboost.log_model(
                self.model,
                artifact_path="xgboost_model",
                signature=signature,
                registered_model_name=os.getenv(
                    "MLFLOW_REGISTERED_MODEL", "used_cars_price_model"
                ),
            )

            # artefato: feature importances em JSON
            fi = dict(zip(
                self.feature_names or [],
                self.model.feature_importances_.tolist(),
            ))
            mlflow.log_dict(fi, "feature_importances.json")
            mlflow.log_dict(metrics, "metrics.json")

            logger.info(
                "MLflow run '%s' finalizado — R²=%.4f RMSE=%.2f  [%s]",
                run_name, metrics.get("r2", 0), metrics.get("rmse", 0),
                run.info.run_id,
            )
    
    def predict(self, df: pd.DataFrame, return_std: bool = True) -> Tuple[pd.Series, pd.Series]:
        """Faz previsões com intervalos de confiança usando bootstrap."""
        X = self.prepare_features(df, fit=False)

        predictions = pd.Series(self.model.predict(X), index=df.index)

        if return_std:
            rng = np.random.default_rng(seed=42)
            n_bootstrap = 100
            bootstrap_predictions = []

            base_params = {k: v for k, v in self.model.get_params().items()}
            base_params['random_state'] = 42

            for i in range(n_bootstrap):
                indices = rng.integers(0, len(X), size=len(X))
                X_boot = X.iloc[indices]
                y_boot = df[self.target].iloc[indices]

                model_boot = xgb.XGBRegressor(**base_params)
                model_boot.fit(X_boot, y_boot)
                bootstrap_predictions.append(model_boot.predict(X))

            uncertainty = pd.Series(
                np.std(bootstrap_predictions, axis=0),
                index=df.index,
            )
            return predictions, uncertainty

        return predictions, None
    
    def analyze_residuals(self, y_true: pd.Series, y_pred: pd.Series) -> Dict[str, Any]:
        """Analisa resíduos do modelo."""
        residuals = y_true - y_pred
        
        # Estatísticas básicas
        stats_dict = {
            'residuals_mean': float(np.mean(residuals)),
            'residuals_std': float(np.std(residuals)),
            'residuals_skew': float(stats.skew(residuals)),
            'residuals_kurtosis': float(stats.kurtosis(residuals))
        }
        
        # Teste de normalidade
        _, shapiro_p = stats.shapiro(residuals)
        stats_dict['residuals_normality_p'] = float(shapiro_p)
        
        # Teste de heterocedasticidade
        _, white_p = self._white_test(y_pred, residuals)
        stats_dict['heteroscedasticity_test'] = (None, float(white_p))
        
        return stats_dict
    
    def get_feature_importance(self, df: pd.DataFrame = None, method: str = 'gain') -> pd.Series:
        """
        Retorna importância das features.

        Args:
            df:     DataFrame necessário quando method='shap' (usado para calcular os
                    valores SHAP sobre uma amostra representativa).
            method: 'gain' (padrão) usa importância nativa do XGBoost;
                    'shap' calcula importância via SHAP TreeExplainer.
        """
        if method == 'shap':
            if df is None:
                raise ValueError("Parâmetro 'df' é obrigatório quando method='shap'.")
            X = self.prepare_features(df, fit=False)
            explainer = shap.TreeExplainer(self.model)
            shap_values = explainer.shap_values(X)
            importance = pd.Series(
                np.abs(shap_values).mean(axis=0),
                index=self.feature_names,
            )
        else:
            importance = pd.Series(
                self.model.feature_importances_,
                index=self.feature_names,
            )

        return importance.sort_values(ascending=False)
    
    # ── persistência ──────────────────────────────────────────────────────────

    def save(
        self,
        models_dir: Path | str = _MODELS_DIR,
        tag: str = "",
    ) -> Path:
        """
        Serializa o modelo completo (XGBoost + encoders + scaler + metadados)
        em dois arquivos:
          - models/price_model_{timestamp}{tag}.joblib  (versão versionada)
          - models/price_model_latest.joblib             (sempre a mais recente)

        Retorna o caminho do arquivo versionado.
        """
        models_dir = Path(models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{tag}" if tag else ""
        versioned_path = models_dir / f"price_model_{ts}{suffix}.joblib"

        payload = {
            "model": self.model,
            "label_encoders": self.label_encoders,
            "scaler": self.scaler,
            "categorical_features": self.categorical_features,
            "numerical_features": self.numerical_features,
            "target": self.target,
            "feature_names": self.feature_names,
            "saved_at": ts,
            "version": f"{ts}{suffix}",
        }
        joblib.dump(payload, versioned_path, compress=3)

        # sempre sobrescreve o "latest"
        latest_path = models_dir / "price_model_latest.joblib"
        joblib.dump(payload, latest_path, compress=3)

        # salva metadados legíveis em JSON
        meta_path = models_dir / f"price_model_{ts}{suffix}_meta.json"
        meta = {
            "version": payload["version"],
            "saved_at": ts,
            "categorical_features": self.categorical_features,
            "numerical_features": self.numerical_features,
            "target": self.target,
            "feature_names": self.feature_names,
            "model_params": self.model.get_params(),
        }
        meta_path.write_text(json.dumps(meta, indent=2))

        # latest.txt aponta para o arquivo mais recente
        (models_dir / "latest.txt").write_text(str(versioned_path))

        # ── loga o joblib no run MLflow ativo (se existir) ──────────────────
        if _mlflow_active() and self._active_run_id:
            try:
                with mlflow.start_run(run_id=self._active_run_id):
                    mlflow.log_artifact(str(versioned_path), artifact_path="joblib")
                    mlflow.log_artifact(str(meta_path), artifact_path="joblib")
                logger.info("Artefato joblib logado no run MLflow %s", self._active_run_id)
            except Exception as exc:
                logger.warning("Falha ao logar joblib no MLflow: %s", exc)

        logger.info("Modelo salvo em %s", versioned_path)
        return versioned_path

    @classmethod
    def load(cls, path: Path | str = "latest") -> "AdvancedPriceModel":
        """
        Carrega modelo do disco.

        Args:
            path: caminho explícito do .joblib, ou 'latest' para carregar
                  automaticamente models/price_model_latest.joblib.
        """
        if str(path) == "latest":
            candidate = _MODELS_DIR / "price_model_latest.joblib"
        else:
            candidate = Path(path)

        if not candidate.exists():
            raise FileNotFoundError(
                f"Modelo não encontrado em '{candidate}'.\n"
                "Execute scripts/train_model.py para gerar o primeiro artefato."
            )

        payload = joblib.load(candidate)
        instance = cls(
            categorical_features=payload["categorical_features"],
            numerical_features=payload["numerical_features"],
            target=payload["target"],
        )
        instance.model = payload["model"]
        instance.label_encoders = payload["label_encoders"]
        instance.scaler = payload["scaler"]
        instance.feature_names = payload["feature_names"]
        logger.info("Modelo carregado de '%s' (versão %s)", candidate, payload.get("version"))
        return instance

    @classmethod
    def load_or_train(
        cls,
        df: pd.DataFrame,
        categorical_features: List[str],
        numerical_features: List[str],
        target: str = "price",
        models_dir: Path | str = _MODELS_DIR,
        validation_method: str = "time_series",
    ) -> Tuple["AdvancedPriceModel", Dict[str, float], bool]:
        """
        Carrega modelo do disco se existir; caso contrário treina, salva e retorna.

        Returns:
            (model, metrics, from_cache)
              from_cache=True  → carregado do disco
              from_cache=False → treinado agora
        """
        models_dir = Path(models_dir)
        latest = models_dir / "price_model_latest.joblib"

        if latest.exists():
            try:
                model = cls.load("latest")
                return model, {}, True
            except Exception as exc:
                logger.warning("Falha ao carregar modelo salvo (%s). Retreinando…", exc)

        model = cls(categorical_features, numerical_features, target)
        metrics = model.train(df, validation_method=validation_method)
        model.save(models_dir=models_dir)
        return model, metrics, False

    def _white_test(self, y_pred: pd.Series, residuals: pd.Series) -> Tuple[float, float]:
        """Implementa teste de White para heterocedasticidade."""
        # Criar termos quadráticos
        X = pd.DataFrame({
            'pred': y_pred,
            'pred2': y_pred ** 2
        })
        
        # Regressão dos resíduos quadrados
        resid2 = residuals ** 2
        
        # Calcular R² da regressão auxiliar
        r2 = np.corrcoef(X['pred'], resid2)[0, 1] ** 2
        
        # Estatística do teste
        n = len(y_pred)
        stat = n * r2
        p_value = 1 - stats.chi2.cdf(stat, df=2)
        
        return stat, p_value 
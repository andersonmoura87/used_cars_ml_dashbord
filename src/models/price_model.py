import pandas as pd
import numpy as np
from typing import Dict, Tuple, List, Any
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import LabelEncoder, RobustScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import shap
import logging
from datetime import datetime
import statsmodels.api as sm
from scipy import stats

logger = logging.getLogger(__name__)

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
        
        self.feature_names = None
        
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepara features para o modelo."""
        X = pd.DataFrame()
        
        # Codificar variáveis categóricas
        for col in self.categorical_features:
            if col in df.columns:
                X[col] = self.label_encoders[col].fit_transform(df[col].fillna('missing'))
        
        # Escalar variáveis numéricas
        if self.numerical_features:
            numeric_data = df[self.numerical_features].fillna(df[self.numerical_features].median())
            X[self.numerical_features] = self.scaler.fit_transform(numeric_data)
        
        self.feature_names = X.columns.tolist()
        return X
    
    def train(self, df: pd.DataFrame, validation_method: str = 'time_series') -> Dict[str, float]:
        """Treina o modelo com validação robusta."""
        X = self.prepare_features(df)
        y = df[self.target]
        
        if validation_method == 'time_series':
            # Validação temporal
            tscv = TimeSeriesSplit(n_splits=5)
            scores = cross_val_score(
                self.model, X, y,
                cv=tscv,
                scoring=['r2', 'neg_mean_squared_error', 'neg_mean_absolute_error']
            )
            
            metrics = {
                'r2': float(np.mean(scores['test_r2'])),
                'rmse': float(np.sqrt(-np.mean(scores['test_neg_mean_squared_error']))),
                'mae': float(-np.mean(scores['test_neg_mean_absolute_error']))
            }
        else:
            # Treinar no conjunto completo
            self.model.fit(X, y)
            
            # Calcular métricas
            y_pred = self.model.predict(X)
            metrics = {
                'r2': float(self.model.score(X, y)),
                'rmse': float(np.sqrt(np.mean((y - y_pred) ** 2))),
                'mae': float(np.mean(np.abs(y - y_pred)))
            }
        
        return metrics
    
    def predict(self, df: pd.DataFrame, return_std: bool = True) -> Tuple[pd.Series, pd.Series]:
        """Faz previsões com intervalos de confiança usando bootstrap."""
        X = self.prepare_features(df)
        
        # Previsão base
        predictions = pd.Series(self.model.predict(X), index=df.index)
        
        if return_std:
            # Bootstrap para estimar incerteza
            n_bootstrap = 100
            bootstrap_predictions = []
            
            for _ in range(n_bootstrap):
                # Amostragem bootstrap dos dados
                indices = np.random.choice(len(X), size=len(X), replace=True)
                X_boot = X.iloc[indices]
                y_boot = df[self.target].iloc[indices]
                
                # Treinar modelo no bootstrap
                model_boot = xgb.XGBRegressor(**self.model.get_params())
                model_boot.fit(X_boot, y_boot)
                
                # Fazer previsões
                bootstrap_predictions.append(model_boot.predict(X))
            
            # Calcular desvio padrão das previsões
            uncertainty = pd.Series(
                np.std(bootstrap_predictions, axis=0),
                index=df.index
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
    
    def get_feature_importance(self, method: str = 'gain') -> pd.Series:
        """Retorna importância das features."""
        if method == 'shap':
            # Calcular valores SHAP
            explainer = shap.TreeExplainer(self.model)
            shap_values = explainer.shap_values(X)
            
            # Calcular importância média absoluta
            importance = pd.Series(
                np.abs(shap_values).mean(axis=0),
                index=self.feature_names
            )
        else:
            # Usar importância do XGBoost
            importance = pd.Series(
                self.model.feature_importances_,
                index=self.feature_names
            )
        
        return importance.sort_values(ascending=False)
    
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
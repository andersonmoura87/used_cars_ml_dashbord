import pandas as pd
import numpy as np
from sklearn.preprocessing import RobustScaler
from sklearn.impute import KNNImputer
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.covariance import EmpiricalCovariance
import logging
from typing import Dict, Tuple, List, Any
from scipy import stats

logger = logging.getLogger(__name__)

class RobustDataQuality:
    """Classe para análise robusta de qualidade de dados."""
    
    def __init__(self):
        self.scaler = RobustScaler()
        self.imputer = KNNImputer(n_neighbors=5)
        self.knn_imputer = KNNImputer(n_neighbors=5)
        self.isolation_forest = IsolationForest(contamination=0.1, random_state=42)
        self.lof = LocalOutlierFactor(contamination=0.1)
        self.numerical_columns = None
        self.categorical_columns = None
        
    def analyze_distributions(self, df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """Analisa distribuições das variáveis numéricas."""
        distributions = {}
        
        for col in df.select_dtypes(include=[np.number]).columns:
            data = df[col].dropna()
            if len(data) == 0:
                continue
                
            # Calcular estatísticas robustas
            median = data.median()
            mad = stats.median_abs_deviation(data)
            q1, q3 = data.quantile([0.25, 0.75])
            iqr = q3 - q1
            
            # Teste de normalidade
            _, shapiro_p = stats.shapiro(data.sample(min(len(data), 5000)))
            
            distributions[col] = {
                'median': float(median),
                'mad': float(mad),
                'iqr': float(iqr),
                'skewness': float(stats.skew(data)),
                'kurtosis': float(stats.kurtosis(data)),
                'shapiro_p': float(shapiro_p)
            }
        
        return distributions
    
    def detect_multivariate_outliers(self, df: pd.DataFrame) -> pd.Series:
        """Detecta outliers usando distância de Mahalanobis."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            return pd.Series(False, index=df.index)
        
        # Preparar dados
        X = df[numeric_cols].copy()
        X = X.fillna(X.median())
        X_scaled = self.scaler.fit_transform(X)
        
        # Calcular distância de Mahalanobis
        covariance = np.cov(X_scaled.T)
        inv_covariance = np.linalg.pinv(covariance)
        mean = np.mean(X_scaled, axis=0)
        
        distances = []
        for i in range(len(X_scaled)):
            diff = X_scaled[i] - mean
            dist = np.sqrt(diff.dot(inv_covariance).dot(diff))
            distances.append(dist)
        
        # Identificar outliers usando limiar baseado em chi-quadrado
        threshold = np.sqrt(stats.chi2.ppf(0.975, df=len(numeric_cols)))
        outliers = pd.Series(distances, index=df.index) > threshold
        
        return outliers
    
    def impute_missing_values(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Imputa valores faltantes usando KNN para numéricos e moda para categóricos."""
        df_clean = df.copy()
        imputation_stats = {}
        
        # Imputação para variáveis numéricas
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            numeric_data = df[numeric_cols]
            missing_before = numeric_data.isnull().sum()
            
            if missing_before.sum() > 0:
                numeric_imputed = pd.DataFrame(
                    self.imputer.fit_transform(numeric_data),
                    columns=numeric_cols,
                    index=df.index
                )
                df_clean[numeric_cols] = numeric_imputed
                
                for col in numeric_cols:
                    imputation_stats[col] = {
                        'missing_before': int(missing_before[col]),
                        'missing_after': 0,
                        'imputation_method': 'knn'
                    }
        
        # Imputação para variáveis categóricas
        categorical_cols = df.select_dtypes(exclude=[np.number]).columns
        for col in categorical_cols:
            missing_before = df[col].isnull().sum()
            if missing_before > 0:
                mode_values = df[col].mode()
                if not mode_values.empty:
                    mode_value = mode_values.iloc[0]
                    df_clean[col] = df_clean[col].fillna(mode_value)
                
                imputation_stats[col] = {
                    'missing_before': int(missing_before),
                    'missing_after': int(df_clean[col].isnull().sum()),
                    'imputation_method': 'mode'
                }
        
        return df_clean, imputation_stats
    
    def _find_correlated_categories(self, df: pd.DataFrame, target_col: str) -> List[str]:
        """Encontra colunas categóricas correlacionadas usando Chi-square."""
        correlated_cols = []
        for col in self.categorical_columns:
            if col != target_col:
                contingency_table = pd.crosstab(
                    df[target_col].fillna('MISSING'),
                    df[col].fillna('MISSING')
                )
                _, p_value, _, _ = stats.chi2_contingency(contingency_table)
                if p_value < self.significance_level:
                    correlated_cols.append(col)
        return correlated_cols
    
    def _conditional_mode_imputation(
        self, df: pd.DataFrame, target_col: str, corr_cols: List[str]
    ) -> pd.Series:
        """Imputa valores usando moda condicional baseada em variáveis correlacionadas."""
        result = df[target_col].copy()
        
        # Criar grupos baseados nas variáveis correlacionadas
        grouped = df.groupby(corr_cols)[target_col]
        
        # Para cada valor nulo, encontrar a moda do seu grupo
        for idx in df[df[target_col].isnull()].index:
            group_key = tuple(df.loc[idx, corr_cols])
            try:
                mode_value = grouped.get_group(group_key).mode()[0]
            except:
                mode_value = df[target_col].mode()[0]
            result[idx] = mode_value
            
        return result
    
    def _calculate_imputation_statistics(
        self, original_df: pd.DataFrame, imputed_df: pd.DataFrame
    ) -> Dict:
        """Calcula estatísticas sobre a imputação."""
        stats = {}
        
        for col in original_df.columns:
            missing_count = original_df[col].isnull().sum()
            if missing_count > 0:
                if col in self.numerical_columns:
                    # Para variáveis numéricas, calcular diferença nas distribuições
                    stats[col] = {
                        'missing_count': missing_count,
                        'missing_percentage': missing_count / len(original_df) * 100,
                        'original_mean': original_df[col].mean(),
                        'imputed_mean': imputed_df[col].mean(),
                        'original_std': original_df[col].std(),
                        'imputed_std': imputed_df[col].std(),
                        'ks_test': stats.ks_2samp(
                            original_df[col].dropna(),
                            imputed_df[col]
                        ).pvalue
                    }
                else:
                    # Para variáveis categóricas, calcular mudanças na distribuição
                    orig_dist = original_df[col].value_counts(normalize=True)
                    imp_dist = imputed_df[col].value_counts(normalize=True)
                    stats[col] = {
                        'missing_count': missing_count,
                        'missing_percentage': missing_count / len(original_df) * 100,
                        'category_changes': (orig_dist - imp_dist).to_dict()
                    }
        
        return stats 
import pandas as pd
import numpy as np
from datetime import datetime
import json
from pathlib import Path
import logging
from typing import Dict, List, Optional, Union
import yaml
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataMonitor:
    """Classe para monitoramento de qualidade dos dados e detecção de drift."""
    
    def __init__(
        self,
        config_path: str = "config/data_cleaning.yaml"
    ):
        self.config = self._load_config(config_path)
        self.metrics_path = Path(self.config['monitoring']['metrics_export']['path'])
        self.reference_data = None
        
    def _load_config(self, config_path: str) -> Dict:
        """Carrega configurações do YAML."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _calculate_numeric_metrics(
        self,
        df: pd.DataFrame,
        columns: List[str]
    ) -> Dict:
        """Calcula métricas para colunas numéricas."""
        metrics = {}
        
        for col in columns:
            if col not in df.columns:
                continue
                
            col_metrics = df[col].describe()
            metrics[col] = {
                'mean': float(col_metrics['mean']),
                'std': float(col_metrics['std']),
                'min': float(col_metrics['min']),
                'max': float(col_metrics['max']),
                'q1': float(col_metrics['25%']),
                'median': float(col_metrics['50%']),
                'q3': float(col_metrics['75%']),
                'missing_rate': float(df[col].isnull().mean()),
                'unique_count': int(df[col].nunique())
            }
            
            # Detectar outliers
            q1, q3 = col_metrics['25%'], col_metrics['75%']
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            metrics[col]['outliers_count'] = int(
                ((df[col] < lower_bound) | (df[col] > upper_bound)).sum()
            )
            
        return metrics
    
    def _calculate_categorical_metrics(
        self,
        df: pd.DataFrame,
        columns: List[str]
    ) -> Dict:
        """Calcula métricas para colunas categóricas."""
        metrics = {}
        
        for col in columns:
            if col not in df.columns:
                continue
                
            value_counts = df[col].value_counts()
            metrics[col] = {
                'unique_count': int(df[col].nunique()),
                'missing_rate': float(df[col].isnull().mean()),
                'mode': str(df[col].mode().iloc[0]) if not df[col].mode().empty else None,
                'top_values': value_counts.head(5).to_dict(),
                'entropy': float(stats.entropy(value_counts.values))
            }
            
        return metrics
    
    def calculate_metrics(
        self,
        df: pd.DataFrame,
        numeric_columns: List[str],
        categorical_columns: List[str]
    ) -> Dict:
        """Calcula métricas completas do dataset."""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'row_count': len(df),
            'column_count': len(df.columns),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024**2,
            'numeric_metrics': self._calculate_numeric_metrics(df, numeric_columns),
            'categorical_metrics': self._calculate_categorical_metrics(df, categorical_columns)
        }
        
        return metrics
    
    def detect_drift(
        self,
        current_data: pd.DataFrame,
        reference_data: Optional[pd.DataFrame] = None,
        threshold: float = 0.05
    ) -> Dict:
        """Detecta drift nos dados usando testes estatísticos."""
        if reference_data is None:
            if self.reference_data is None:
                ref_path = Path(self.config['monitoring']['drift_detection']['reference_data'])
                if not ref_path.exists():
                    raise ValueError("Dados de referência não encontrados")
                reference_data = pd.read_parquet(ref_path)
            else:
                reference_data = self.reference_data
        
        drift_metrics = {
            'timestamp': datetime.now().isoformat(),
            'numeric_drift': {},
            'categorical_drift': {}
        }
        
        # Drift em variáveis numéricas (Kolmogorov-Smirnov test)
        for col in self.config['data_quality']['validation_rules'].keys():
            if col not in current_data.columns or col not in reference_data.columns:
                continue
                
            ks_statistic, p_value = stats.ks_2samp(
                reference_data[col].dropna(),
                current_data[col].dropna()
            )
            
            drift_metrics['numeric_drift'][col] = {
                'statistic': float(ks_statistic),
                'p_value': float(p_value),
                'has_drift': bool(p_value < threshold)
            }
        
        # Drift em variáveis categóricas (Chi-square test)
        for col in self.config['data_quality']['categorical_mappings'].keys():
            if col not in current_data.columns or col not in reference_data.columns:
                continue
                
            ref_counts = reference_data[col].value_counts()
            cur_counts = current_data[col].value_counts()
            
            # Alinhar categorias
            all_categories = sorted(set(ref_counts.index) | set(cur_counts.index))
            ref_counts = ref_counts.reindex(all_categories, fill_value=0)
            cur_counts = cur_counts.reindex(all_categories, fill_value=0)
            
            chi2_statistic, p_value = stats.chi2_contingency(
                [ref_counts.values, cur_counts.values]
            )[:2]
            
            drift_metrics['categorical_drift'][col] = {
                'statistic': float(chi2_statistic),
                'p_value': float(p_value),
                'has_drift': bool(p_value < threshold)
            }
        
        return drift_metrics
    
    def save_metrics(self, metrics: Dict) -> None:
        """Salva métricas em arquivo JSON."""
        # Criar diretório se não existir
        date_str = datetime.now().strftime('%Y%m%d')
        metrics_dir = Path(str(self.metrics_path).format(date=date_str))
        metrics_dir.parent.mkdir(parents=True, exist_ok=True)
        
        with open(metrics_dir, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"Métricas salvas em {metrics_dir}")
    
    def plot_drift_analysis(
        self,
        current_data: pd.DataFrame,
        reference_data: pd.DataFrame,
        save_path: Optional[str] = None
    ) -> None:
        """Gera visualizações para análise de drift."""
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            # Configurar estilo
            plt.style.use('seaborn')
            
            # Criar subplots para cada variável numérica
            numeric_cols = list(self.config['data_quality']['validation_rules'].keys())
            n_cols = len(numeric_cols)
            
            fig, axes = plt.subplots(
                n_cols,
                2,
                figsize=(15, 5 * n_cols)
            )
            
            for i, col in enumerate(numeric_cols):
                # Boxplot
                sns.boxplot(
                    data=pd.concat([
                        reference_data[[col]].assign(type='reference'),
                        current_data[[col]].assign(type='current')
                    ]),
                    x='type',
                    y=col,
                    ax=axes[i, 0]
                )
                axes[i, 0].set_title(f'Boxplot - {col}')
                
                # Densidade
                sns.kdeplot(
                    data=reference_data[col].dropna(),
                    label='reference',
                    ax=axes[i, 1]
                )
                sns.kdeplot(
                    data=current_data[col].dropna(),
                    label='current',
                    ax=axes[i, 1]
                )
                axes[i, 1].set_title(f'Densidade - {col}')
                axes[i, 1].legend()
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path)
                logger.info(f"Gráficos salvos em {save_path}")
            else:
                plt.show()
                
        except ImportError:
            logger.warning("matplotlib e seaborn são necessários para visualizações")
            
if __name__ == "__main__":
    # Exemplo de uso
    monitor = DataMonitor()
    
    # Carregar dados atuais
    current_data = pd.read_parquet("data/cleansed/used_cars.parquet")
    
    # Calcular métricas
    metrics = monitor.calculate_metrics(
        current_data,
        numeric_columns=['price', 'year', 'odometer'],
        categorical_columns=['manufacturer', 'model', 'condition', 'fuel']
    )
    
    # Salvar métricas
    monitor.save_metrics(metrics)
    
    # Se houver dados de referência, detectar drift
    try:
        reference_data = pd.read_parquet("data/reference/used_cars_reference.parquet")
        drift_metrics = monitor.detect_drift(current_data, reference_data)
        
        # Salvar métricas de drift
        drift_path = Path("metrics") / datetime.now().strftime('%Y%m%d') / "drift_metrics.json"
        with open(drift_path, 'w') as f:
            json.dump(drift_metrics, f, indent=2)
            
        # Gerar visualizações
        monitor.plot_drift_analysis(
            current_data,
            reference_data,
            save_path="reports/drift_analysis.png"
        )
        
    except FileNotFoundError:
        logger.warning("Dados de referência não encontrados. Pulando detecção de drift.") 
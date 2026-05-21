import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataCleaner:
    """Classe para limpeza e validação de dados."""
    
    def __init__(
        self,
        input_path: str,
        output_path: str,
        config: Optional[Dict] = None
    ):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.config = config or {}
        
        # Configurações padrão
        self.numeric_columns = self.config.get('numeric_columns', [
            'price', 'year', 'odometer'
        ])
        self.categorical_columns = self.config.get('categorical_columns', [
            'manufacturer', 'model', 'condition', 'fuel', 'title_status',
            'transmission', 'drive', 'type', 'paint_color', 'state'
        ])
        self.date_columns = self.config.get('date_columns', ['posting_date'])
        
        # Limites para validação
        self.validation_rules = self.config.get('validation_rules', {
            'year': {'min': 1900, 'max': datetime.now().year + 1},
            'price': {'min': 100, 'max': 1000000},
            'odometer': {'min': 0, 'max': 1000000}
        })
    
    def read_data(self) -> pd.DataFrame:
        """Lê os dados do arquivo de entrada."""
        logger.info(f"Lendo dados de {self.input_path}")
        
        if self.input_path.suffix == '.csv':
            df = pd.read_csv(self.input_path)
        elif self.input_path.suffix == '.parquet':
            df = pd.read_parquet(self.input_path)
        else:
            raise ValueError(f"Formato de arquivo não suportado: {self.input_path.suffix}")
        
        logger.info(f"Dados lidos com sucesso. Shape: {df.shape}")
        return df
    
    def clean_numeric_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpa e valida colunas numéricas."""
        df_clean = df.copy()
        
        for col in self.numeric_columns:
            if col not in df_clean.columns:
                continue
                
            # Converter para numérico
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            
            # Aplicar regras de validação
            if col in self.validation_rules:
                rules = self.validation_rules[col]
                mask = df_clean[col].between(rules['min'], rules['max'])
                df_clean.loc[~mask, col] = np.nan
                
                logger.info(f"Coluna {col}: {(~mask).sum()} valores inválidos removidos")
        
        return df_clean
    
    def clean_categorical_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpa e padroniza colunas categóricas."""
        df_clean = df.copy()
        
        for col in self.categorical_columns:
            if col not in df_clean.columns:
                continue
                
            # Converter para string
            df_clean[col] = df_clean[col].astype(str)
            
            # Limpar espaços e converter para minúsculas
            df_clean[col] = df_clean[col].str.strip().str.lower()
            
            # Substituir valores inválidos por NaN
            df_clean.loc[df_clean[col].isin(['nan', 'none', '']), col] = np.nan
            
            logger.info(f"Coluna {col}: {df_clean[col].isnull().sum()} valores nulos")
        
        return df_clean
    
    def clean_date_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpa e converte colunas de data."""
        df_clean = df.copy()
        
        for col in self.date_columns:
            if col not in df_clean.columns:
                continue
                
            # Converter para datetime
            df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce')
            
            logger.info(f"Coluna {col}: {df_clean[col].isnull().sum()} valores nulos")
        
        return df_clean
    
    def remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove registros duplicados."""
        n_before = len(df)
        df_clean = df.drop_duplicates()
        n_removed = n_before - len(df_clean)
        
        logger.info(f"Removidos {n_removed} registros duplicados")
        return df_clean
    
    def save_data(self, df: pd.DataFrame, format: str = 'parquet') -> None:
        """Salva os dados limpos."""
        # Criar diretório se não existir
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == 'parquet':
            # Salvar como Parquet com compressão
            table = pa.Table.from_pandas(df)
            pq.write_table(
                table,
                self.output_path,
                compression='snappy'
            )
        else:
            # Salvar como CSV
            df.to_csv(self.output_path, index=False)
        
        logger.info(f"Dados salvos em {self.output_path}")
    
    def generate_quality_report(self, df: pd.DataFrame) -> Dict:
        """Gera relatório de qualidade dos dados."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'n_rows': len(df),
            'n_columns': len(df.columns),
            'memory_usage': df.memory_usage(deep=True).sum() / 1024**2,  # MB
            'null_counts': df.isnull().sum().to_dict(),
            'column_types': df.dtypes.astype(str).to_dict()
        }
        
        # Estatísticas para colunas numéricas
        numeric_stats = {}
        for col in self.numeric_columns:
            if col in df.columns:
                stats = df[col].describe()
                numeric_stats[col] = {
                    'mean': float(stats['mean']),
                    'std': float(stats['std']),
                    'min': float(stats['min']),
                    'max': float(stats['max'])
                }
        report['numeric_stats'] = numeric_stats
        
        # Estatísticas para colunas categóricas
        categorical_stats = {}
        for col in self.categorical_columns:
            if col in df.columns:
                value_counts = df[col].value_counts()
                categorical_stats[col] = {
                    'unique_values': len(value_counts),
                    'top_values': value_counts.head(5).to_dict()
                }
        report['categorical_stats'] = categorical_stats
        
        return report
    
    def run_pipeline(self) -> None:
        """Executa o pipeline completo de limpeza."""
        try:
            # Ler dados
            df = self.read_data()
            
            # Aplicar limpezas
            df = self.clean_numeric_columns(df)
            df = self.clean_categorical_columns(df)
            df = self.clean_date_columns(df)
            df = self.remove_duplicates(df)
            
            # Gerar relatório
            report = self.generate_quality_report(df)
            
            # Salvar dados e relatório
            self.save_data(df)
            
            # Salvar relatório
            report_path = self.output_path.parent / 'quality_report.json'
            import json
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info("Pipeline de limpeza concluído com sucesso!")
            
        except Exception as e:
            logger.error(f"Erro no pipeline de limpeza: {str(e)}")
            raise

if __name__ == "__main__":
    # Exemplo de uso
    cleaner = DataCleaner(
        input_path="data/raw/used_cars.csv",
        output_path="data/cleansed/used_cars.parquet"
    )
    cleaner.run_pipeline() 
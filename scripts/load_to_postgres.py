import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, Table, Column, MetaData
from sqlalchemy.types import Integer, Float, String, DateTime, Boolean
import logging
from pathlib import Path
import pyarrow.parquet as pq
from datetime import datetime
from typing import Dict, Optional
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PostgresLoader:
    """Classe para carregar dados no PostgreSQL."""
    
    def __init__(
        self,
        input_path: str,
        table_name: str,
        schema: str = 'public',
        if_exists: str = 'replace',
        chunk_size: int = 10000
    ):
        self.input_path = Path(input_path)
        self.table_name = table_name
        self.schema = schema
        self.if_exists = if_exists
        self.chunk_size = chunk_size
        
        # Criar engine
        self.engine = self._create_engine()
        
        # Mapeamento de tipos
        self.dtype_mapping = {
            'int64': Integer,
            'float64': Float,
            'object': String,
            'datetime64[ns]': DateTime,
            'bool': Boolean
        }
    
    def _create_engine(self) -> create_engine:
        """Cria conexão com o banco de dados."""
        connection_string = (
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
            f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
        )
        
        return create_engine(
            connection_string,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            connect_args={
                'client_encoding': 'utf8',
                'options': '-c client_encoding=utf8'
            }
        )
    
    def _get_sql_dtypes(self, df: pd.DataFrame) -> Dict:
        """Define tipos SQL para as colunas."""
        sql_dtypes = {}
        
        for col, dtype in df.dtypes.items():
            if str(dtype) in self.dtype_mapping:
                sql_dtypes[col] = self.dtype_mapping[str(dtype)]
            else:
                sql_dtypes[col] = String
        
        return sql_dtypes
    
    def _create_table_if_not_exists(self, df: pd.DataFrame) -> None:
        """Cria tabela se não existir."""
        metadata = MetaData()
        
        # Definir colunas
        columns = []
        sql_dtypes = self._get_sql_dtypes(df)
        
        for col_name, sql_type in sql_dtypes.items():
            columns.append(Column(col_name, sql_type))
        
        # Criar tabela
        Table(
            self.table_name,
            metadata,
            *columns,
            schema=self.schema
        )
        
        # Criar no banco
        metadata.create_all(self.engine)
        logger.info(f"Tabela {self.schema}.{self.table_name} criada/verificada")
    
    def load_data(self, df: Optional[pd.DataFrame] = None) -> None:
        """
        Carrega dados no banco de dados PostgreSQL.
        
        Args:
            df: DataFrame opcional com os dados a serem carregados.
                 Se não fornecido, lê do input_path.
        """
        try:
            # Se não recebeu DataFrame, lê do arquivo
            if df is None:
                if self.input_path.suffix == '.parquet':
                    df = pd.read_parquet(self.input_path)
                else:
                    df = pd.read_csv(self.input_path)
            
            # Garantir tipos de dados corretos
            if 'id' in df.columns:
                df['id'] = df['id'].astype('int64')
            if 'price' in df.columns:
                df['price'] = pd.to_numeric(df['price'], errors='coerce')
            if 'odometer' in df.columns:
                df['odometer'] = pd.to_numeric(df['odometer'], errors='coerce')
            if 'year' in df.columns:
                df['year'] = pd.to_numeric(df['year'], errors='coerce').astype('Int64')
            if 'posting_date' in df.columns:
                df['posting_date'] = pd.to_datetime(df['posting_date'], errors='coerce')
            
            # Criar tabela se não existir
            self._create_table_if_not_exists(df)
            
            # Carregar dados em chunks
            chunk_size = self.chunk_size or len(df)
            total_rows = len(df)
            
            for i in range(0, total_rows, chunk_size):
                chunk = df.iloc[i:i + chunk_size]
                chunk.to_sql(
                    self.table_name,
                    self.engine,
                    schema=self.schema,
                    if_exists=self.if_exists if i == 0 else 'append',
                    index=False,
                    method='multi'
                )
                logger.info(f"Carregados {min(i + chunk_size, total_rows)} de {total_rows} registros")
            
            logger.info(f"Total de {total_rows} registros carregados com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {str(e)}")
            raise
    
    def _create_indices(self) -> None:
        """Cria índices na tabela."""
        try:
            # Índices para colunas mais usadas em filtros
            index_columns = [
                'manufacturer',
                'model',
                'year',
                'price',
                'state'
            ]
            
            for col in index_columns:
                index_name = f"idx_{self.table_name}_{col}"
                query = text(
                    f"CREATE INDEX IF NOT EXISTS {index_name} "
                    f"ON {self.schema}.{self.table_name} ({col})"
                )
                
                with self.engine.connect() as conn:
                    conn.execute(query)
                    conn.commit()
                
                logger.info(f"Índice criado: {index_name}")
            
        except Exception as e:
            logger.error(f"Erro ao criar índices: {str(e)}")
            raise
    
    def validate_load(self) -> Dict:
        """Valida o carregamento dos dados."""
        try:
            with self.engine.connect() as conn:
                # Contar registros
                count_query = text(
                    f"SELECT COUNT(*) FROM {self.schema}.{self.table_name}"
                )
                total_rows = conn.execute(count_query).scalar()
                
                # Verificar valores nulos
                null_counts = {}
                for col in self._get_sql_dtypes(pd.read_parquet(self.input_path)):
                    query = text(
                        f"SELECT COUNT(*) FROM {self.schema}.{self.table_name} "
                        f"WHERE {col} IS NULL"
                    )
                    null_count = conn.execute(query).scalar()
                    null_counts[col] = null_count
                
                return {
                    'total_rows': total_rows,
                    'null_counts': null_counts,
                    'validation_timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Erro na validação: {str(e)}")
            raise

if __name__ == "__main__":
    # Exemplo de uso
    loader = PostgresLoader(
        input_path="data/cleansed/cars.parquet",
        table_name="cars",
        schema="public",
        if_exists="replace"
    )
    
    # Carregar dados
    loader.load_data()
    
    # Validar carregamento
    validation_report = loader.validate_load()
    
    # Salvar relatório de validação
    import json
    with open("data/cleansed/load_validation_report.json", "w") as f:
        json.dump(validation_report, f, indent=2) 
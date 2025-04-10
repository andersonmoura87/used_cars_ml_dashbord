import pandas as pd
import sqlalchemy as sa
from pathlib import Path
import logging
from typing import Dict
import json
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CarMarketAnalyzer:
    """Classe para análise do mercado de carros usados."""
    
    def __init__(self, connection_string: str):
        self.engine = sa.create_engine(connection_string)
        self.results_path = Path("reports/market_analysis")
        self.results_path.mkdir(parents=True, exist_ok=True)
    
    def average_price_by_manufacturer(self) -> pd.DataFrame:
        """1. Preço médio dos veículos por fabricante."""
        query = """
        SELECT 
            manufacturer,
            COUNT(*) as total_cars,
            ROUND(AVG(price)::numeric, 2) as avg_price,
            ROUND(MIN(price)::numeric, 2) as min_price,
            ROUND(MAX(price)::numeric, 2) as max_price
        FROM used_cars
        WHERE manufacturer IS NOT NULL
            AND price IS NOT NULL
            AND price BETWEEN 100 AND 1000000
        GROUP BY manufacturer
        ORDER BY avg_price DESC
        """
        return pd.read_sql(query, self.engine)
    
    def top_models_by_mileage(self) -> pd.DataFrame:
        """2. Top 5 modelos mais anunciados e quilometragem média."""
        query = """
        WITH top_models AS (
            SELECT model,
                COUNT(*) as total_listings
            FROM used_cars
            WHERE model IS NOT NULL
            GROUP BY model
            ORDER BY total_listings DESC
            LIMIT 5
        )
        SELECT 
            m.model,
            m.total_listings,
            ROUND(AVG(c.odometer)::numeric, 2) as avg_mileage,
            ROUND(AVG(c.price)::numeric, 2) as avg_price
        FROM top_models m
        JOIN used_cars c ON m.model = c.model
        WHERE c.odometer IS NOT NULL
            AND c.odometer BETWEEN 0 AND 1000000
        GROUP BY m.model, m.total_listings
        ORDER BY m.total_listings DESC
        """
        return pd.read_sql(query, self.engine)
    
    def fuel_type_analysis(self) -> pd.DataFrame:
        """3. Top 3 tipos de combustível e quilometragem média."""
        query = """
        WITH top_fuels AS (
            SELECT fuel,
                COUNT(*) as total_cars
            FROM used_cars
            WHERE fuel IS NOT NULL
            GROUP BY fuel
            ORDER BY total_cars DESC
            LIMIT 3
        )
        SELECT 
            f.fuel,
            f.total_cars,
            ROUND(AVG(c.odometer)::numeric, 2) as avg_mileage,
            ROUND(AVG(c.price)::numeric, 2) as avg_price
        FROM top_fuels f
        JOIN used_cars c ON f.fuel = c.fuel
        WHERE c.odometer IS NOT NULL
            AND c.odometer BETWEEN 0 AND 1000000
        GROUP BY f.fuel, f.total_cars
        ORDER BY f.total_cars DESC
        """
        return pd.read_sql(query, self.engine)
    
    def top_regions_by_price(self) -> pd.DataFrame:
        """4. Top 5 regiões com maiores preços médios."""
        query = """
        SELECT 
            region,
            COUNT(*) as total_cars,
            ROUND(AVG(price)::numeric, 2) as avg_price,
            ROUND(MIN(price)::numeric, 2) as min_price,
            ROUND(MAX(price)::numeric, 2) as max_price
        FROM used_cars
        WHERE region IS NOT NULL
            AND price IS NOT NULL
            AND price BETWEEN 100 AND 1000000
        GROUP BY region
        ORDER BY avg_price DESC
        LIMIT 5
        """
        return pd.read_sql(query, self.engine)
    
    def transmission_distribution(self) -> pd.DataFrame:
        """5. Proporção de transmissão manual vs automática."""
        query = """
        WITH transmission_counts AS (
            SELECT 
                transmission,
                COUNT(*) as total
            FROM used_cars
            WHERE transmission IN ('manual', 'automatic')
            GROUP BY transmission
        ),
        total AS (
            SELECT SUM(total) as grand_total
            FROM transmission_counts
        )
        SELECT 
            t.transmission,
            t.total,
            ROUND((t.total::float / tt.grand_total * 100)::numeric, 2) as percentage
        FROM transmission_counts t
        CROSS JOIN total tt
        ORDER BY t.total DESC
        """
        return pd.read_sql(query, self.engine)
    
    def run_all_analyses(self) -> Dict:
        """Executa todas as análises e salva resultados."""
        analyses = {
            'manufacturer_prices': self.average_price_by_manufacturer(),
            'top_models': self.top_models_by_mileage(),
            'fuel_types': self.fuel_type_analysis(),
            'top_regions': self.top_regions_by_price(),
            'transmission_dist': self.transmission_distribution()
        }
        
        # Salvar resultados
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for name, df in analyses.items():
            # Salvar como CSV
            csv_path = self.results_path / f"{name}_{timestamp}.csv"
            df.to_csv(csv_path, index=False)
            
            # Salvar como JSON
            json_path = self.results_path / f"{name}_{timestamp}.json"
            df.to_json(json_path, orient='records', indent=2)
            
            logger.info(f"Análise {name} salva em {csv_path}")
        
        return analyses

if __name__ == "__main__":
    # Configurar conexão
    connection_string = (
        "postgresql://{user}:{password}@{host}:{port}/{database}"
        .format(
            user="seu_usuario",
            password="sua_senha",
            host="localhost",
            port=5432,
            database="mobato"
        )
    )
    
    # Executar análises
    analyzer = CarMarketAnalyzer(connection_string)
    results = analyzer.run_all_analyses()
    
    # Log dos resultados
    for name, df in results.items():
        print(f"\n=== {name} ===")
        print(df) 
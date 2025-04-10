import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
from pathlib import Path
import logging
import json
from typing import Dict, List, Tuple
from scipy import stats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DescriptiveAnalyzer:
    def __init__(self, db_connection_string: str):
        """Initialize the analyzer with database connection."""
        self.engine = create_engine(db_connection_string)
        self.reports_dir = Path('reports/descriptive_analysis')
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure plot style
        plt.style.use('seaborn')
        sns.set_palette('husl')
        plt.rcParams['figure.figsize'] = [12, 6]

    def analyze_price_distribution(self) -> Dict:
        """Analyze the distribution of vehicle prices."""
        logger.info("Analyzing price distribution...")
        
        query = """
        WITH price_stats AS (
            SELECT 
                COUNT(*) as total_count,
                ROUND(AVG(price)::numeric, 2) as mean_price,
                ROUND(STDDEV(price)::numeric, 2) as std_price,
                ROUND(MIN(price)::numeric, 2) as min_price,
                ROUND(MAX(price)::numeric, 2) as max_price,
                ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY price)::numeric, 2) as q1,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price)::numeric, 2) as median,
                ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY price)::numeric, 2) as q3
            FROM cars_cleaned
            WHERE price BETWEEN 5000 AND 1000000
        )
        SELECT 
            *,
            ROUND((mean_price - median) / std_price::numeric, 4) as skewness,
            ROUND(((q3 - q1) / median)::numeric, 4) as relative_iqr
        FROM price_stats;
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Create visualization
        plt.figure(figsize=(12, 6))
        sns.histplot(
            data=pd.read_sql("SELECT price FROM cars_cleaned WHERE price BETWEEN 5000 AND 1000000", self.engine),
            x='price',
            bins=50
        )
        plt.title('Vehicle Price Distribution')
        plt.xlabel('Price ($)')
        plt.ylabel('Frequency')
        plt.axvline(df['median'].iloc[0], color='red', linestyle='--', label='Median')
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'price_distribution.png')
        plt.close()
        
        return df.to_dict(orient='records')[0]

    def analyze_year_price_relationship(self) -> Dict:
        """Analyze the relationship between manufacturing year and average price."""
        logger.info("Analyzing year-price relationship...")
        
        query = """
        SELECT 
            year,
            COUNT(*) as total_vehicles,
            ROUND(AVG(price)::numeric, 2) as avg_price,
            ROUND(STDDEV(price)::numeric, 2) as price_std,
            ROUND(MIN(price)::numeric, 2) as min_price,
            ROUND(MAX(price)::numeric, 2) as max_price
        FROM cars_cleaned
        WHERE year >= 1990 AND year <= 2024
        AND price BETWEEN 5000 AND 1000000
        GROUP BY year
        ORDER BY year;
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Calculate correlation
        correlation = stats.pearsonr(df['year'], df['avg_price'])
        
        # Create visualization
        plt.figure(figsize=(12, 6))
        sns.regplot(data=df, x='year', y='avg_price', scatter_kws={'alpha':0.5})
        plt.title('Average Price by Manufacturing Year')
        plt.xlabel('Year')
        plt.ylabel('Average Price ($)')
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'year_price_relationship.png')
        plt.close()
        
        return {
            'data': df.to_dict(orient='records'),
            'correlation': {
                'coefficient': correlation[0],
                'p_value': correlation[1]
            }
        }

    def analyze_mileage_distribution(self) -> Dict:
        """Analyze mileage distribution by fuel type and manufacturer."""
        logger.info("Analyzing mileage distribution...")
        
        query = """
        SELECT 
            manufacturer,
            fuel,
            COUNT(*) as total_vehicles,
            ROUND(AVG(odometer)::numeric, 2) as avg_mileage,
            ROUND(STDDEV(odometer)::numeric, 2) as mileage_std,
            ROUND(MIN(odometer)::numeric, 2) as min_mileage,
            ROUND(MAX(odometer)::numeric, 2) as max_mileage
        FROM cars_cleaned
        WHERE manufacturer != 'unknown'
        AND fuel != 'unknown'
        AND odometer > 0
        GROUP BY manufacturer, fuel
        HAVING COUNT(*) >= 10
        ORDER BY manufacturer, avg_mileage DESC;
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Create visualization
        plt.figure(figsize=(15, 8))
        sns.boxplot(data=df, x='manufacturer', y='avg_mileage', hue='fuel')
        plt.title('Average Mileage by Manufacturer and Fuel Type')
        plt.xticks(rotation=45)
        plt.xlabel('Manufacturer')
        plt.ylabel('Average Mileage')
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'mileage_distribution.png')
        plt.close()
        
        return df.to_dict(orient='records')

    def analyze_price_mileage_correlation(self) -> Dict:
        """Analyze correlation between price and mileage."""
        logger.info("Analyzing price-mileage correlation...")
        
        query = """
        SELECT 
            price,
            odometer
        FROM cars_cleaned
        WHERE price BETWEEN 5000 AND 1000000
        AND odometer > 0;
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Calculate correlation
        correlation = stats.pearsonr(df['odometer'], df['price'])
        
        # Create visualization
        plt.figure(figsize=(12, 6))
        sns.regplot(data=df, x='odometer', y='price', scatter_kws={'alpha':0.1})
        plt.title('Price vs Mileage Correlation')
        plt.xlabel('Mileage')
        plt.ylabel('Price ($)')
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'price_mileage_correlation.png')
        plt.close()
        
        return {
            'correlation': {
                'coefficient': correlation[0],
                'p_value': correlation[1]
            }
        }

    def detect_price_outliers(self) -> Dict:
        """Identify price outliers using IQR method."""
        logger.info("Detecting price outliers...")
        
        query = """
        WITH price_stats AS (
            SELECT 
                price,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY price) as q1,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY price) as q3
            FROM cars_cleaned
            WHERE price BETWEEN 5000 AND 1000000
        ),
        iqr_calc AS (
            SELECT 
                DISTINCT q1, q3,
                (q3 - q1) * 1.5 as iqr_range
            FROM price_stats
        )
        SELECT 
            COUNT(*) as total_vehicles,
            COUNT(*) FILTER (WHERE price < q1 - iqr_range) as low_outliers,
            COUNT(*) FILTER (WHERE price > q3 + iqr_range) as high_outliers,
            ROUND(AVG(price) FILTER (WHERE price BETWEEN q1 - iqr_range AND q3 + iqr_range)::numeric, 2) as avg_normal_price
        FROM price_stats, iqr_calc;
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Create boxplot
        plt.figure(figsize=(12, 6))
        sns.boxplot(
            data=pd.read_sql("SELECT price FROM cars_cleaned WHERE price BETWEEN 5000 AND 1000000", self.engine),
            x='price'
        )
        plt.title('Price Distribution with Outliers')
        plt.xlabel('Price ($)')
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'price_outliers.png')
        plt.close()
        
        return df.to_dict(orient='records')[0]

    def run_all_analyses(self) -> None:
        """Run all descriptive analyses and save results."""
        logger.info("Running all descriptive analyses...")
        
        results = {
            'price_distribution': self.analyze_price_distribution(),
            'year_price_relationship': self.analyze_year_price_relationship(),
            'mileage_distribution': self.analyze_mileage_distribution(),
            'price_mileage_correlation': self.analyze_price_mileage_correlation(),
            'price_outliers': self.detect_price_outliers()
        }
        
        # Save results to JSON
        with open(self.reports_dir / 'descriptive_analysis_results.json', 'w') as f:
            json.dump(results, f, indent=4)
        
        logger.info("All analyses completed. Results saved to reports/descriptive_analysis/")

if __name__ == "__main__":
    # Example usage
    db_connection = "postgresql://user:password@localhost:5432/cars_db"  # Replace with actual connection string
    analyzer = DescriptiveAnalyzer(db_connection)
    analyzer.run_all_analyses() 
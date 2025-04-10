import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
from pathlib import Path
import logging
import json
from typing import Dict, List, Tuple
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AdvancedMarketAnalyzer:
    def __init__(self, db_connection_string: str):
        """Initialize the analyzer with database connection."""
        self.engine = create_engine(db_connection_string)
        self.reports_dir = Path('reports/market_analysis')
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure plot style
        plt.style.use('seaborn')
        sns.set_palette('husl')
        plt.rcParams['figure.figsize'] = [12, 6]

    def analyze_value_retention(self) -> Dict:
        """Analyze how different models retain their value over time and mileage."""
        logger.info("Analyzing value retention by model...")
        
        query = """
        WITH vehicle_metrics AS (
            SELECT 
                manufacturer,
                model,
                year,
                price,
                odometer,
                (2024 - year) as age,
                price / NULLIF(odometer, 0) * 1000 as price_per_1000_miles
            FROM cars_cleaned
            WHERE odometer > 0
        )
        SELECT 
            manufacturer,
            model,
            ROUND(AVG(price)::numeric, 2) as avg_price,
            ROUND(AVG(age)::numeric, 1) as avg_age,
            ROUND(AVG(price_per_1000_miles)::numeric, 2) as avg_price_per_1000_miles,
            COUNT(*) as total_vehicles
        FROM vehicle_metrics
        GROUP BY manufacturer, model
        HAVING COUNT(*) >= 10
        ORDER BY avg_price_per_1000_miles DESC
        LIMIT 15;
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Create visualization
        plt.figure(figsize=(12, 6))
        sns.barplot(data=df.head(10), x='model', y='price_per_1000_miles', hue='manufacturer')
        plt.xticks(rotation=45)
        plt.title('Top 10 Models - Price per 1000 Miles')
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'value_retention.png')
        plt.close()
        
        return df.to_dict(orient='records')

    def analyze_seasonality(self) -> Dict:
        """Analyze seasonal patterns in sales and prices."""
        logger.info("Analyzing market seasonality...")
        
        query = """
        SELECT 
            EXTRACT(MONTH FROM posting_date) as month,
            COUNT(*) as total_listings,
            ROUND(AVG(price)::numeric, 2) as avg_price,
            ROUND(MIN(price)::numeric, 2) as min_price,
            ROUND(MAX(price)::numeric, 2) as max_price
        FROM cars_cleaned
        WHERE posting_date IS NOT NULL
        GROUP BY EXTRACT(MONTH FROM posting_date)
        ORDER BY month;
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Create visualizations
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        sns.barplot(data=df, x='month', y='total_listings', ax=ax1)
        ax1.set_title('Total Listings by Month')
        ax1.set_xlabel('Month')
        ax1.set_ylabel('Total Listings')
        
        sns.lineplot(data=df, x='month', y='avg_price', ax=ax2)
        ax2.set_title('Average Price by Month')
        ax2.set_xlabel('Month')
        ax2.set_ylabel('Average Price ($)')
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'seasonality.png')
        plt.close()
        
        return df.to_dict(orient='records')

    def analyze_color_price_relationships(self) -> Dict:
        """Analyze the relationship between vehicle colors and prices by type."""
        logger.info("Analyzing color-price relationships...")
        
        query = """
        SELECT 
            type,
            paint_color,
            COUNT(*) as total_vehicles,
            ROUND(AVG(price)::numeric, 2) as avg_price,
            ROUND(AVG(odometer)::numeric, 2) as avg_mileage
        FROM cars_cleaned
        WHERE type != 'unknown' 
        AND paint_color != 'unknown'
        GROUP BY type, paint_color
        HAVING COUNT(*) > 10
        ORDER BY type, avg_price DESC;
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Create heatmap
        pivot_table = df.pivot(index='type', columns='paint_color', values='avg_price')
        plt.figure(figsize=(12, 8))
        sns.heatmap(pivot_table, annot=True, fmt='.0f', cmap='YlOrRd')
        plt.title('Average Price by Vehicle Type and Color')
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'color_price_heatmap.png')
        plt.close()
        
        return df.to_dict(orient='records')

    def analyze_geographical_patterns(self) -> Dict:
        """Analyze geographical patterns in pricing."""
        logger.info("Analyzing geographical price patterns...")
        
        query = """
        WITH state_metrics AS (
            SELECT 
                state,
                COUNT(*) as total_listings,
                ROUND(AVG(price)::numeric, 2) as avg_price,
                ROUND(STDDEV(price)::numeric, 2) as price_stddev,
                ROUND(AVG(odometer)::numeric, 2) as avg_mileage
            FROM cars_cleaned
            WHERE state IS NOT NULL
            GROUP BY state
            HAVING COUNT(*) >= 50
        )
        SELECT 
            state,
            total_listings,
            avg_price,
            price_stddev,
            avg_mileage,
            ROUND((price_stddev / avg_price * 100)::numeric, 2) as price_variation_pct
        FROM state_metrics
        ORDER BY price_variation_pct DESC;
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Create visualizations
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        sns.barplot(data=df.sort_values('avg_price', ascending=False).head(10),
                   x='state', y='avg_price', ax=ax1)
        ax1.set_title('Top 10 States by Average Price')
        ax1.set_xlabel('State')
        ax1.set_ylabel('Average Price ($)')
        plt.xticks(rotation=45)
        
        sns.scatterplot(data=df, x='total_listings', y='avg_price', ax=ax2)
        ax2.set_title('Average Price vs Total Listings by State')
        ax2.set_xlabel('Total Listings')
        ax2.set_ylabel('Average Price ($)')
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'geographical_analysis.png')
        plt.close()
        
        return df.to_dict(orient='records')

    def run_all_analyses(self) -> None:
        """Run all analyses and save results."""
        logger.info("Running all market analyses...")
        
        results = {
            'value_retention': self.analyze_value_retention(),
            'seasonality': self.analyze_seasonality(),
            'color_price': self.analyze_color_price_relationships(),
            'geographical': self.analyze_geographical_patterns()
        }
        
        # Save results to JSON
        with open(self.reports_dir / 'market_analysis_results.json', 'w') as f:
            json.dump(results, f, indent=4)
        
        logger.info("All analyses completed. Results saved to reports/market_analysis/")

if __name__ == "__main__":
    # Example usage
    db_connection = "postgresql://user:password@localhost:5432/cars_db"  # Replace with actual connection string
    analyzer = AdvancedMarketAnalyzer(db_connection)
    analyzer.run_all_analyses() 
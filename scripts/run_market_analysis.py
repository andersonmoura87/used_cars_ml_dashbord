import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import logging
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database connection settings
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "used_cars")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# Create database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def get_db_connection():
    """Create and return a database connection."""
    try:
        engine = create_engine(DATABASE_URL)
        logger.info("Database connection established")
        return engine
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        raise

def extract_queries(sql_content):
    """Extract SQL queries from content, ignoring comments."""
    # Split content by semicolon to separate queries
    raw_queries = sql_content.split(';')
    
    queries = []
    for raw_query in raw_queries:
        # Remove comments and empty lines
        lines = []
        for line in raw_query.split('\n'):
            line = line.strip()
            if line and not line.startswith('--'):
                lines.append(line)
        
        # Join lines back together
        query = ' '.join(lines)
        if query.strip():
            # Find the first SELECT statement
            if 'SELECT' in query:
                query = query[query.find('SELECT'):]
                queries.append(query)
    
    return queries

def read_sql_file(file_path):
    """Read SQL queries from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            sql_content = file.read()
        return extract_queries(sql_content)
    except Exception as e:
        logger.error(f"Error reading SQL file: {str(e)}")
        raise

def run_analysis(engine, query, output_file):
    """Execute a query and save results to CSV."""
    try:
        # Execute query
        df = pd.read_sql_query(query, engine)
        
        # Create output directory if it doesn't exist
        os.makedirs('data/analysis', exist_ok=True)
        
        # Save results to CSV
        output_path = os.path.join('data/analysis', f"{output_file}.csv")
        df.to_csv(output_path, index=False)
        logger.info(f"Results saved to {output_path}")
        
        # Display summary
        logger.info(f"\nAnalysis Summary for {output_file}:")
        logger.info("-" * 50)
        logger.info(f"Total rows: {len(df)}")
        logger.info(f"Columns: {', '.join(df.columns)}")
        if len(df) > 0:
            for col in df.columns:
                if df[col].dtype in ['int64', 'float64']:
                    logger.info(f"{col} - Avg: {df[col].mean():.2f}, Min: {df[col].min():.2f}, Max: {df[col].max():.2f}")
        logger.info("-" * 50)
        
    except Exception as e:
        logger.error(f"Error running analysis: {str(e)}")
        raise

def main():
    """Main function to run all analyses."""
    try:
        # Get database connection
        engine = get_db_connection()
        
        # Read SQL queries
        sql_file = 'sql/analysis/market_analysis.sql'
        queries = read_sql_file(sql_file)
        
        # Analysis names
        analysis_names = [
            'manufacturer_price_analysis',
            'top_5_models',
            'top_3_fuel_types',
            'top_5_states_by_price',
            'transmission_distribution',
            'financing_by_manufacturer'
        ]
        
        # Run each analysis
        for query, name in zip(queries, analysis_names):
            logger.info(f"Running analysis: {name}")
            logger.debug(f"Query: {query}")  # Debug log to see the actual query
            run_analysis(engine, query, name)
            
        logger.info("All analyses completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
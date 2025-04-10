import os
import sys
import logging
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from pathlib import Path

# Add src directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.etl.transform import transform_data, calculate_market_statistics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/etl.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_db_connection():
    """
    Create database connection from environment variables.
    """
    load_dotenv()
    
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "used_cars")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    
    return create_engine(
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        pool_size=5,
        max_overflow=10
    )

def load_raw_data():
    """
    Load raw data from CSV file.
    """
    raw_data_path = os.getenv("RAW_DATA_PATH", "data/raw/used_cars.csv")
    logger.info(f"Loading raw data from {raw_data_path}")
    
    try:
        df = pd.read_csv(raw_data_path)
        logger.info(f"Loaded {len(df)} records")
        return df
    except Exception as e:
        logger.error(f"Error loading raw data: {str(e)}")
        raise

def save_processed_data(df, engine):
    """
    Save processed data to database.
    """
    logger.info("Saving processed data to database")
    
    try:
        # Save cars data
        df.to_sql('cars', engine, if_exists='replace', index=False)
        logger.info(f"Saved {len(df)} car records")
        
        # Calculate and save market statistics
        stats = calculate_market_statistics(df)
        
        # Save manufacturer statistics
        stats['manufacturer'].to_sql('manufacturer_stats', engine, if_exists='replace', index=False)
        logger.info(f"Saved {len(stats['manufacturer'])} manufacturer statistics")
        
        # Save state statistics
        stats['state'].to_sql('state_stats', engine, if_exists='replace', index=False)
        logger.info(f"Saved {len(stats['state'])} state statistics")
        
        # Save year statistics
        stats['year'].to_sql('year_stats', engine, if_exists='replace', index=False)
        logger.info(f"Saved {len(stats['year'])} year statistics")
        
    except Exception as e:
        logger.error(f"Error saving processed data: {str(e)}")
        raise

def main():
    """
    Main ETL process.
    """
    try:
        logger.info("Starting ETL process")
        
        # Get database connection
        engine = get_db_connection()
        
        # Load raw data
        df_raw = load_raw_data()
        
        # Transform data
        df_processed = transform_data(df_raw)
        
        # Save processed data
        save_processed_data(df_processed, engine)
        
        logger.info("ETL process completed successfully")
        
    except Exception as e:
        logger.error(f"ETL process failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
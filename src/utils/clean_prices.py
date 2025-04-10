import pandas as pd
import numpy as np
from typing import Tuple
import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine

def get_db_connection():
    """
    Create a database connection using environment variables
    """
    load_dotenv()
    
    DB_NAME = os.getenv('DB_NAME')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')
    
    # Create SQLAlchemy engine for pandas
    engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')
    return engine

def clean_prices(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Clean price data based on identified issues and decisions documented in docs/data_cleaning_decisions.md
    
    Args:
        df: DataFrame containing vehicle data
        
    Returns:
        Tuple containing:
        - Cleaned DataFrame
        - DataFrame with removed records for audit purposes
    """
    print(f"Initial record count: {len(df)}")
    
    # Create a copy to avoid modifying the original
    df_clean = df.copy()
    df_removed = pd.DataFrame()
    
    # 1. Remove the extreme high price case
    extreme_high_mask = df_clean['price'] == 987654321
    removed_count = extreme_high_mask.sum()
    df_removed = pd.concat([df_removed, df_clean[extreme_high_mask]])
    df_clean = df_clean[~extreme_high_mask]
    print(f"Records removed due to extreme high price: {removed_count}")
    
    # 2. Remove duplicate Dodge Charger listings with suspicious prices
    charger_mask = (
        (df_clean['manufacturer'].str.lower() == 'dodge') & 
        (df_clean['model'].str.lower() == 'charger') & 
        (df_clean['price'] == 199) &
        (df_clean['year'] == 2017)
    )
    # Keep only the first occurrence of suspicious Dodge Charger listings
    duplicate_chargers = df_clean[charger_mask]
    if not duplicate_chargers.empty:
        df_removed = pd.concat([df_removed, duplicate_chargers.iloc[1:]])
        df_clean = pd.concat([
            df_clean[~charger_mask],  # Non-Charger records
            duplicate_chargers.iloc[:1]  # Keep first Charger
        ])
    removed_count = len(duplicate_chargers) - 1 if not duplicate_chargers.empty else 0
    print(f"Duplicate Dodge Charger records removed: {removed_count}")
    
    # 3. Correct specific prices based on descriptions
    # Honda correction
    honda_mask = (
        (df_clean['manufacturer'].str.lower() == 'honda') & 
        (df_clean['price'] == 80)
    )
    corrected_count = honda_mask.sum()
    df_clean.loc[honda_mask, 'price'] = 800
    print(f"Honda prices corrected: {corrected_count}")
    
    # Cadillac Escalade correction
    escalade_mask = (
        (df_clean['manufacturer'].str.lower() == 'cadillac') & 
        (df_clean['model'].str.lower() == 'escalade esv') & 
        (df_clean['price'] == 1)
    )
    corrected_count = escalade_mask.sum()
    df_clean.loc[escalade_mask, 'price'] = 5500
    print(f"Cadillac prices corrected: {corrected_count}")
    
    # 4. Handle monthly payment listings
    # First, identify monthly payment listings
    monthly_payment_mask = df_clean['description'].str.contains('month|payment', case=False, na=False)
    removed_count = monthly_payment_mask.sum()
    df_removed = pd.concat([df_removed, df_clean[monthly_payment_mask]])
    df_clean = df_clean[~monthly_payment_mask]
    print(f"Monthly payment listings removed: {removed_count}")
    
    # 5. Remove remaining suspicious prices
    # Very low prices (below $500) that aren't part of special cases
    suspicious_low_mask = df_clean['price'] < 500
    removed_count = suspicious_low_mask.sum()
    df_removed = pd.concat([df_removed, df_clean[suspicious_low_mask]])
    df_clean = df_clean[~suspicious_low_mask]
    print(f"Records removed due to suspicious low prices: {removed_count}")
    
    # Very high prices (above $1M) that aren't part of special cases
    suspicious_high_mask = df_clean['price'] > 1000000
    removed_count = suspicious_high_mask.sum()
    df_removed = pd.concat([df_removed, df_clean[suspicious_high_mask]])
    df_clean = df_clean[~suspicious_high_mask]
    print(f"Records removed due to suspicious high prices: {removed_count}")
    
    # Reset index for both dataframes
    df_clean = df_clean.reset_index(drop=True)
    df_removed = df_removed.reset_index(drop=True)
    
    print(f"Final record count: {len(df_clean)}")
    print(f"Total records removed: {len(df_removed)}")
    
    return df_clean, df_removed

def validate_cleaning(df_clean: pd.DataFrame, df_removed: pd.DataFrame) -> dict:
    """
    Validate the cleaning process and return statistics
    
    Args:
        df_clean: Cleaned DataFrame
        df_removed: DataFrame with removed records
        
    Returns:
        Dictionary with validation statistics
    """
    stats = {
        'original_count': len(df_clean) + len(df_removed),
        'cleaned_count': len(df_clean),
        'removed_count': len(df_removed),
        'removed_percentage': (len(df_removed) / (len(df_clean) + len(df_removed))) * 100,
        'price_stats_clean': df_clean['price'].describe(),
        'price_stats_removed': df_removed['price'].describe(),
        'states_affected': sorted(df_removed['state'].unique().tolist()),
        'years_affected': sorted(df_removed['year'].unique().tolist())
    }
    
    return stats

if __name__ == "__main__":
    # Get database connection
    engine = get_db_connection()
    
    # Load data from database
    print("Loading data from database...")
    df = pd.read_sql("SELECT * FROM cars", engine)
    print(f"Loaded {len(df)} records")
    
    # Clean the data
    print("\nCleaning data...")
    df_clean, df_removed = clean_prices(df)
    
    # Validate the cleaning
    stats = validate_cleaning(df_clean, df_removed)
    
    # Print validation statistics
    print("\nCleaning Statistics:")
    print("=" * 50)
    print(f"Original records: {stats['original_count']}")
    print(f"Cleaned records: {stats['cleaned_count']}")
    print(f"Removed records: {stats['removed_count']}")
    print(f"Removed percentage: {stats['removed_percentage']:.2f}%")
    
    print("\nStates affected:", stats['states_affected'])
    print("Years affected:", stats['years_affected'])
    
    print("\nPrice statistics after cleaning:")
    print(stats['price_stats_clean'])
    
    print("\nPrice statistics of removed records:")
    print(stats['price_stats_removed'])
    
    # Save cleaned data back to database
    print("\nSaving cleaned data back to database...")
    df_clean.to_sql('cars_cleaned', engine, if_exists='replace', index=False)
    df_removed.to_sql('cars_removed', engine, if_exists='replace', index=False)
    print("Data saved successfully!")
    
    # Also save to CSV for backup
    output_dir = 'data'
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, 'used_cars_cleaned.csv')
    df_clean.to_csv(output_path, index=False)
    print(f"\nBackup saved to CSV: {output_path}")
    
    removed_path = os.path.join(output_dir, 'used_cars_removed.csv')
    df_removed.to_csv(removed_path, index=False)
    print(f"Removed records saved to CSV: {removed_path}") 
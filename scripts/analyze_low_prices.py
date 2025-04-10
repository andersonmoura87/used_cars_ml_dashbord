import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import logging
from pathlib import Path
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/low_price_analysis.log'),
        logging.StreamHandler()
    ]
)

def load_data():
    """Load the cleaned data from CSV file."""
    try:
        df = pd.read_csv('data/processed/used_cars_cleaned.csv')
        logging.info(f"Loaded {len(df)} records from cleaned data")
        return df
    except Exception as e:
        logging.error(f"Error loading data: {str(e)}")
        raise

def extract_financing_info(description):
    """Extract financing information from description."""
    result = {
        'down_payment': None,
        'monthly_payment': None,
        'term_months': None,
        'apr': None,
        'real_price': None
    }
    
    try:
        # Extract down payment
        down_pattern = r'entrada\s*(?:de\s*)?R?\$?\s*(\d+(?:\.\d{3})*(?:,\d{2})?)'
        down_match = re.search(down_pattern, description.lower())
        if down_match:
            down_value = down_match.group(1).replace('.', '').replace(',', '.')
            result['down_payment'] = float(down_value)
        
        # Extract monthly payment
        monthly_pattern = r'(?:parcela|parcelas)\s*(?:de\s*)?R?\$?\s*(\d+(?:\.\d{3})*(?:,\d{2})?)'
        monthly_match = re.search(monthly_pattern, description.lower())
        if monthly_match:
            monthly_value = monthly_match.group(1).replace('.', '').replace(',', '.')
            result['monthly_payment'] = float(monthly_value)
        
        # Extract term in months
        term_pattern = r'(\d+)\s*(?:x|parcelas|vezes)'
        term_match = re.search(term_pattern, description.lower())
        if term_match:
            result['term_months'] = int(term_match.group(1))
        
        # Extract APR
        apr_pattern = r'(\d+(?:,\d+)?)%\s*(?:a\.a\.|ao ano)'
        apr_match = re.search(apr_pattern, description.lower())
        if apr_match:
            apr_value = apr_match.group(1).replace(',', '.')
            result['apr'] = float(apr_value)
        
        # Calculate real price if we have enough information
        if result['monthly_payment'] and result['term_months'] and result['down_payment']:
            result['real_price'] = (result['monthly_payment'] * result['term_months']) + result['down_payment']
            
    except Exception as e:
        logging.warning(f"Error extracting financing info: {str(e)}")
    
    return result

def analyze_low_prices(df):
    """Analyze cars with suspiciously low prices."""
    # Define price thresholds
    min_price = 5000  # Minimum reasonable price
    suspicious_threshold = 10000  # Price below which we should investigate
    
    # Filter low price cars
    low_price_cars = df[df['price'] < suspicious_threshold].copy()
    logging.info(f"Found {len(low_price_cars)} cars with prices below {suspicious_threshold}")
    
    # Extract financing information
    low_price_cars['financing_info'] = low_price_cars['description'].apply(extract_financing_info)
    
    # Analyze financing patterns
    financing_stats = {
        'total_low_price': len(low_price_cars),
        'with_down_payment': 0,
        'with_monthly_payment': 0,
        'with_term': 0,
        'with_real_price': 0,
        'suspicious_prices': 0
    }
    
    for info in low_price_cars['financing_info']:
        if info['down_payment']:
            financing_stats['with_down_payment'] += 1
        if info['monthly_payment']:
            financing_stats['with_monthly_payment'] += 1
        if info['term_months']:
            financing_stats['with_term'] += 1
        if info['real_price']:
            financing_stats['with_real_price'] += 1
            if info['real_price'] > suspicious_threshold:
                financing_stats['suspicious_prices'] += 1
    
    # Print analysis results
    print("\nLow Price Analysis:")
    print(f"Total cars with prices below {suspicious_threshold}: {financing_stats['total_low_price']}")
    print(f"Cars with down payment information: {financing_stats['with_down_payment']}")
    print(f"Cars with monthly payment information: {financing_stats['with_monthly_payment']}")
    print(f"Cars with term information: {financing_stats['with_term']}")
    print(f"Cars with calculated real price: {financing_stats['with_real_price']}")
    print(f"Potential financing deals (real price > {suspicious_threshold}): {financing_stats['suspicious_prices']}")
    
    # Analyze by manufacturer
    manufacturer_stats = low_price_cars.groupby('manufacturer').agg({
        'price': ['count', 'mean', 'min', 'max'],
        'financing_info': lambda x: sum(1 for info in x if info['real_price'] and info['real_price'] > suspicious_threshold)
    }).round(2)
    
    print("\nLow Price Analysis by Manufacturer:")
    print(manufacturer_stats)
    
    # Save detailed analysis to CSV
    low_price_cars.to_csv('data/analysis/low_price_analysis.csv', index=False)
    logging.info("Saved detailed low price analysis to data/analysis/low_price_analysis.csv")

def main():
    """Main function to run the analysis."""
    try:
        df = load_data()
        analyze_low_prices(df)
    except Exception as e:
        logging.error(f"Error in main function: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
import pandas as pd
import numpy as np
from clean_prices import clean_prices, validate_cleaning

def test_cleaning():
    # Create test data
    test_data = {
        'original_id': range(10),
        'price': [
            987654321,  # Extreme high price
            199,        # Dodge Charger 1
            199,        # Dodge Charger 2 (duplicate)
            199,        # Dodge Charger 3 (duplicate)
            80,         # Honda to be corrected
            1,          # Cadillac to be corrected
            100,        # Suspicious low price
            200000,     # Suspicious high price
            15000,      # Normal price
            25000       # Normal price
        ],
        'manufacturer': [
            'chevrolet',
            'dodge',
            'dodge',
            'dodge',
            'honda',
            'cadillac',
            'ford',
            'ferrari',
            'toyota',
            'honda'
        ],
        'model': [
            'impala',
            'charger',
            'charger',
            'charger',
            'accord',
            'escalade esv',
            'f150',
            'testarossa',
            'camry',
            'civic'
        ],
        'year': [
            1960,
            2017,
            2017,
            2017,
            2004,
            2003,
            2010,
            1990,
            2018,
            2019
        ],
        'state': [
            'al',
            'al',
            'al',
            'al',
            'al',
            'al',
            'al',
            'al',
            'ca',
            'ca'
        ],
        'description': [
            'trade value is higher',
            'monthly payment $199',
            'monthly payment $199',
            'monthly payment $199',
            'Asking $800',
            '$5,500 OBO',
            'great condition',
            'rare model',
            'like new',
            'excellent condition'
        ]
    }
    
    df_test = pd.DataFrame(test_data)
    
    # Apply cleaning
    df_clean, df_removed = clean_prices(df_test)
    
    # Validate results
    stats = validate_cleaning(df_clean, df_removed)
    
    # Print test results
    print("\nTest Results:")
    print("=" * 50)
    print(f"Original records: {stats['original_count']}")
    print(f"Cleaned records: {stats['cleaned_count']}")
    print(f"Removed records: {stats['removed_count']}")
    print(f"Removed percentage: {stats['removed_percentage']:.2f}%")
    
    print("\nCleaned DataFrame:")
    print(df_clean[['original_id', 'price', 'manufacturer', 'model']])
    
    print("\nRemoved DataFrame:")
    print(df_removed[['original_id', 'price', 'manufacturer', 'model']])
    
    # Verify specific corrections
    print("\nVerifying Corrections:")
    print("=" * 50)
    
    # Check Honda price correction
    honda_mask = df_clean['manufacturer'] == 'honda'
    if honda_mask.any():
        honda_price = df_clean[honda_mask]['price'].iloc[0]
        print(f"Honda price corrected from 80 to {honda_price}: {'✓' if honda_price == 800 else '✗'}")
    else:
        print("Honda not found in cleaned data")
    
    # Check Cadillac price correction
    cadillac_mask = df_clean['manufacturer'] == 'cadillac'
    if cadillac_mask.any():
        cadillac_price = df_clean[cadillac_mask]['price'].iloc[0]
        print(f"Cadillac price corrected from 1 to {cadillac_price}: {'✓' if cadillac_price == 5500 else '✗'}")
    else:
        print("Cadillac not found in cleaned data")
    
    # Check Dodge Charger duplicates
    charger_count = len(df_clean[df_clean['model'] == 'charger'])
    print(f"Dodge Charger duplicates removed (should be 1): {charger_count}: {'✓' if charger_count == 1 else '✗'}")
    
    # Check price range limits
    min_price = df_clean['price'].min()
    max_price = df_clean['price'].max()
    print(f"Minimum price within limits (>=500): {'✓' if min_price >= 500 else '✗'}")
    print(f"Maximum price within limits (<=100000): {'✓' if max_price <= 100000 else '✗'}")

if __name__ == "__main__":
    test_cleaning() 
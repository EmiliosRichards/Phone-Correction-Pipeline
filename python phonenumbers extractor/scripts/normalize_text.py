#!/usr/bin/env python3
"""
Script to normalize text from scraped websites.
"""
import sys
import os
import argparse
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.text.normalizer import normalize_latest_data, get_latest_scraping_dir, process_scraped_texts

def main():
    """Main function to normalize text from scraped websites."""
    parser = argparse.ArgumentParser(description='Normalize text from scraped websites.')
    parser.add_argument('--dir', type=str, help='Directory containing scraped data (default: latest)')
    parser.add_argument('--output', type=str, help='Output directory for normalized text')
    
    args = parser.parse_args()
    
    try:
        if args.dir:
            # Use specified directory
            data_dir = Path(args.dir)
            if not data_dir.exists():
                print(f"Error: Directory {data_dir} does not exist!")
                return 1
                
            print(f"Processing files in: {data_dir}")
            stats = process_scraped_texts(str(data_dir))
        else:
            # Use latest directory
            stats = normalize_latest_data()
        
        print(f"\nSuccessfully processed {stats['processed_files']} out of {stats['total_files']} files.")
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""
Script to analyze phone number extraction results.
"""
import sys
import os
import argparse
from pathlib import Path
import json
from datetime import datetime

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analysis.statistics import print_statistics, save_results

def load_results(file_path):
    """Load phone number extraction results from a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_country_distribution(stats):
    """Analyze the distribution of phone numbers by country."""
    country_codes = stats.get('country_codes', {})
    
    if not country_codes:
        print("No country code data available.")
        return
    
    print("\n=== Country Distribution Analysis ===")
    
    # Sort by count
    sorted_countries = sorted(country_codes.items(), key=lambda x: int(x[1]), reverse=True)
    
    # Calculate total
    total = sum(int(count) for _, count in sorted_countries)
    
    # Print distribution
    print(f"\nTotal numbers with country codes: {total}")
    print("\nDistribution by country:")
    
    for code, count in sorted_countries:
        percentage = (int(count) / total * 100) if total > 0 else 0
        print(f"  +{code}: {count} ({percentage:.1f}%)")

def analyze_format_distribution(stats):
    """Analyze the distribution of phone number formats."""
    format_counts = stats.get('format_counts', {})
    
    if not format_counts:
        print("No format data available.")
        return
    
    print("\n=== Format Distribution Analysis ===")
    
    # Sort by count
    sorted_formats = sorted(format_counts.items(), key=lambda x: int(x[1]), reverse=True)
    
    # Calculate total
    total = sum(int(count) for _, count in sorted_formats)
    
    # Print distribution
    print(f"\nTotal numbers: {total}")
    print("\nDistribution by format:")
    
    for format_name, count in sorted_formats:
        percentage = (int(count) / total * 100) if total > 0 else 0
        print(f"  {format_name}: {count} ({percentage:.1f}%)")

def main():
    """Main function to analyze phone number extraction results."""
    parser = argparse.ArgumentParser(description='Analyze phone number extraction results.')
    parser.add_argument('--file', type=str, help='JSON file containing extraction results')
    parser.add_argument('--output', type=str, help='Output directory for analysis results')
    
    args = parser.parse_args()
    
    try:
        # Determine the file to analyze
        if args.file:
            results_file = Path(args.file)
        else:
            # Find the most recent results file
            results_dir = Path("data/results")
            if not results_dir.exists():
                print("Error: No results directory found!")
                return 1
                
            # Find all JSON files in the results directory and its subdirectories
            json_files = list(results_dir.glob("**/phone_numbers.json"))
            
            if not json_files:
                print("Error: No results files found!")
                return 1
                
            # Sort by modification time (most recent first)
            results_file = sorted(json_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
        
        print(f"Analyzing results from: {results_file}")
        
        # Load the results
        stats = load_results(results_file)
        
        # Print basic statistics
        print_statistics(stats)
        
        # Perform additional analyses
        analyze_country_distribution(stats)
        analyze_format_distribution(stats)
        
        # Save analysis results if output directory is specified
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            analysis_file = output_dir / f"analysis_{timestamp}.json"
            
            # Create analysis results
            analysis_results = {
                'source_file': str(results_file),
                'timestamp': timestamp,
                'basic_stats': {
                    'total_websites': stats.get('total_websites', 0),
                    'websites_with_numbers': stats.get('websites_with_numbers', 0),
                    'total_numbers_found': stats.get('total_numbers_found', 0)
                },
                'country_distribution': stats.get('country_codes', {}),
                'format_distribution': stats.get('format_counts', {})
            }
            
            # Save analysis results
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_results, f, indent=2, ensure_ascii=False)
                
            print(f"\nAnalysis results saved to: {analysis_file}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
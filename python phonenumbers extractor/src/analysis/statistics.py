"""
Statistics and analysis module for the Phone Extraction project.
"""
from collections import defaultdict
from typing import List, Dict, Any
from datetime import datetime
import json
import os
from pathlib import Path

def generate_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate statistics from phone number extraction results.
    
    Args:
        results: List of dictionaries containing extraction results for each website
        
    Returns:
        Dictionary containing statistics
    """
    stats = {
        'total_websites': len(results),
        'websites_with_numbers': 0,
        'total_numbers_found': 0,
        'format_counts': defaultdict(int),
        'country_codes': defaultdict(int),
        'errors': [],
        'results': results
    }
    
    # Process each website's results
    for website_result in results:
        if website_result.get('numbers', []):
            stats['websites_with_numbers'] += 1
            stats['total_numbers_found'] += len(website_result['numbers'])
            
            # Count country codes and formats
            for number in website_result['numbers']:
                # Handle format counting based on available data
                # If 'format' key exists, use it directly
                if 'format' in number:
                    stats['format_counts'][number['format']] += 1
                # Otherwise, infer format from the structure or region
                elif 'region' in number:
                    region = number.get('region', 'unknown')
                    if region == 'US':
                        stats['format_counts']['international'] += 1
                    elif region in ['DE', 'AT', 'CH']:
                        stats['format_counts']['german'] += 1
                    else:
                        stats['format_counts']['international'] += 1
                # Fallback if no region info
                else:
                    original = number.get('original', '')
                    if original.startswith('+'):
                        stats['format_counts']['international'] += 1
                    else:
                        stats['format_counts']['local'] += 1

                # Extract country code if present
                # First check if there's a cleaned or e164 format
                e164_number = number.get('e164', '') or number.get('cleaned', '')
                
                # Also check for formatted field which might contain the country code
                formatted = number.get('formatted', '')
                
                if e164_number.startswith('+'):
                    # Country codes can be 1, 2, or 3 digits
                    # Common country codes: +1 (US/Canada), +44 (UK), +49 (Germany), etc.
                    if e164_number.startswith('+1'):
                        country_code = '1'  # North America
                    elif len(e164_number) > 3 and e164_number[1:3].isdigit():
                        # For other country codes, extract the first 2 digits if they form a valid country code
                        country_code = e164_number[1:3]
                    elif len(e164_number) > 2 and e164_number[1:2].isdigit(): # Check length before fallback
                        # Fallback for single-digit country codes (less common)
                        country_code = e164_number[1:2]
                    else:
                        country_code = None # Could not determine code
                
                # If we couldn't extract from e164, try from formatted
                elif formatted.startswith('+'):
                    if formatted.startswith('+1'):
                        country_code = '1'  # North America
                    elif len(formatted) > 3 and formatted[1:3].isdigit():
                        country_code = formatted[1:3]
                    elif len(formatted) > 2 and formatted[1:2].isdigit():
                        country_code = formatted[1:2]
                    else:
                        country_code = None
                else:
                    # Try to extract from original if it has a country code
                    original = number.get('original', '')
                    if '+' in original:
                        # Extract the part after + and before space or bracket
                        import re
                        match = re.search(r'\+(\d{1,3})', original)
                        if match:
                            country_code = match.group(1)
                        else:
                            country_code = None
                    else:
                        country_code = None

                if country_code:
                    stats['country_codes'][country_code] += 1
    
    # Convert defaultdicts to regular dicts for JSON serialization
    stats['format_counts'] = dict(stats['format_counts'])
    stats['country_codes'] = dict(stats['country_codes'])
    
    return stats

def save_results(stats_summary: Dict[str, Any], timestamp: str = None, output_dir: str = None) -> Dict[str, str]:
    """
    Save extraction results and statistics to files.
    
    Args:
        stats_summary: Dictionary containing aggregated statistics.
        timestamp: Optional timestamp string (if None, current time will be used).
        output_dir: Optional output directory (if None, default 'data/results' will be used).
        
    Returns:
        Dictionary containing paths to the saved files.
    """
    if timestamp is None:
        # This ensures timestamp string is created if not passed
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Convert the string timestamp (either passed or generated) to a formatted string for the report
    try:
        report_dt_obj = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
        report_time_str = report_dt_obj.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        # Fallback if the timestamp string is not in the expected format
        report_time_str = "Timestamp N/A"

    # Use custom output directory or default
    base_dir = Path(output_dir or os.environ.get('RESULTS_DIR', "data/results"))
    
    # Create results directory if it doesn't exist
    results_dir = base_dir / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract 'results' from stats_summary. This modifies stats_summary in-place.
    all_extracted_numbers = stats_summary.pop('results', [])
    
    # Create a copy of the modified stats_summary for the JSON file, then add 'results' back.
    json_data = stats_summary.copy()
    json_data['results'] = all_extracted_numbers # Add results back for the comprehensive data.json
    
    # Save all extracted phone numbers and full data to data.json
    json_file = results_dir / "data.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    # phone_numbers.json and statistics.json are no longer created as per plan.
    # data.json contains all necessary information.
    
    # Save text report
    text_file = results_dir / "report.txt"
    with open(text_file, 'w', encoding='utf-8') as f:
        f.write("=== Phone Number Detection Report ===\n")
        f.write(f"Generated: {report_time_str}\n\n")

        f.write("Overall Summary\n")
        f.write("-----------------\n")
        f.write(f"Total websites processed: {stats_summary.get('total_websites', 0)}\n")
        f.write(f"Websites with phone numbers: {stats_summary.get('websites_with_numbers', 0)}\n")
        f.write(f"Total phone numbers found: {stats_summary.get('total_numbers_found', 0)}\n\n")

        f.write("Extraction Metrics\n")
        f.write("------------------\n")
        if stats_summary.get('country_codes'):
            f.write("Country Code Counts:\n")
            for code, count in sorted(stats_summary['country_codes'].items()):
                f.write(f"  +{code}: {count}\n")
        else:
            f.write("Country Code Counts: None\n")
        f.write("\n")

        if stats_summary.get('format_counts'):
            f.write("Number Format Counts:\n")
            for fmt, count in sorted(stats_summary['format_counts'].items()):
                f.write(f"  {fmt}: {count}\n")
        else:
            f.write("Number Format Counts: None\n")
        f.write("\n")

        f.write("Detailed Results by Website\n")
        f.write("---------------------------\n")
        if all_extracted_numbers:
            for website_result in all_extracted_numbers:
                f.write(f"Website: {website_result.get('website', 'Unknown Website')}\n")
                numbers = website_result.get('numbers', [])
                if numbers:
                    f.write("  Extracted Numbers:\n")
                    for number_obj in numbers:
                        e164 = number_obj.get('extraction_details', {}).get('e164')
                        original = number_obj.get('extraction_details', {}).get('original')
                        phone_num_top = number_obj.get('phone_number')

                        display_num = "Number data missing"
                        original_text_display = ""

                        if e164:
                            display_num = e164
                            if original and original != e164: # Show original only if different and present
                                original_text_display = f" (Original: {original})"
                        elif original:
                            display_num = original
                        elif phone_num_top:
                            display_num = phone_num_top
                        
                        f.write(f"    - {display_num}{original_text_display}\n")
                else:
                    f.write("  No phone numbers found\n")
                f.write("\n")
        else:
            f.write("No website data processed or no numbers found in any website.\n\n")

        f.write("Processing Errors (if any)\n")
        f.write("--------------------------\n")
        errors = stats_summary.get('errors', [])
        actual_errors = [e for e in errors if e.get('error')]
        if actual_errors:
            for error_entry in actual_errors:
                f.write(f"  {error_entry.get('website', 'Unknown Website')}: {error_entry.get('error', 'No error message')}\n")
        else:
            f.write("  No errors reported.\n")
        f.write("\n")
    
    return {
        'text': str(text_file),
        'json': str(json_file),  # data.json now contains all statistics and results
        'stats': str(json_file)   # Point 'stats' to data.json as it's the comprehensive file
    }

def print_statistics(stats: Dict[str, Any]) -> None:
    """
    Print statistics to the console.
    
    Args:
        stats: Dictionary containing statistics
    """
    print("\n=== Phone Number Detection Summary ===")
    print(f"\nTotal websites processed: {stats['total_websites']}")
    
    if stats['total_websites'] > 0:
        percentage = (stats['websites_with_numbers'] / stats['total_websites'] * 100)
        print(f"Websites with phone numbers: {stats['websites_with_numbers']} ({percentage:.1f}%)")
    else:
        print(f"Websites with phone numbers: {stats['websites_with_numbers']} (0.0%)")
        
    print(f"Total phone numbers found: {stats['total_numbers_found']}")
    
    print("\nNumber formats found:")
    for format_name, count in stats['format_counts'].items():
        print(f"  {format_name}: {count}")
    
    print("\nCountry codes found:")
    for country_code, count in sorted(stats['country_codes'].items()):
        print(f"  +{country_code}: {count}")
    
    if stats.get('errors', []):
        print("\nErrors encountered:")
        for error in stats['errors']:
            print(f"  {error['website']}: {error['error']}")
#!/usr/bin/env python3
"""
Modified test script for phone number extraction with proper Twilio validation handling.
"""
import sys
import phonenumbers
import logging
from typing import List, Dict, Any, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
PRIORITY_REGIONS = {'DE', 'AT', 'CH'}

def extract_phone_numbers_modified(text: str, default_region: str = 'DE', use_twilio: bool = False) -> List[Dict[str, Any]]:
    """
    Extract phone numbers with optional Twilio validation.
    """
    logger.info(f"Extracting phone numbers with Twilio validation {'enabled' if use_twilio else 'disabled'}")
    
    found_numbers: List[Dict[str, Any]] = []
    seen_e164_numbers: Set[str] = set()  # To avoid duplicates
    
    try:
        # Use PhoneNumberMatcher for extraction
        matcher = phonenumbers.PhoneNumberMatcher(text, default_region)
        for match in matcher:
            number_str = match.raw_string
            parsed_num = match.number
            
            # Basic validation using phonenumbers library
            is_possible = phonenumbers.is_possible_number(parsed_num)
            is_valid = phonenumbers.is_valid_number(parsed_num)
            
            if is_possible and is_valid:
                # Format to E.164 for standardization
                e164_format = phonenumbers.format_number(
                    parsed_num, phonenumbers.PhoneNumberFormat.E164
                )
                
                # Deduplicate based on E.164 format
                if e164_format not in seen_e164_numbers:
                    seen_e164_numbers.add(e164_format)
                    
                    # Get region code
                    region_code = phonenumbers.region_code_for_number(parsed_num)
                    is_priority = region_code in PRIORITY_REGIONS
                    
                    # Create validation result placeholder
                    validation_api = {
                        'api_status': 'not_attempted',
                        'is_valid': True,  # Assume valid based on phonenumbers validation
                        'type': None,
                        'error_message': None,
                        'details': {}
                    }
                    
                    # Only attempt Twilio validation if explicitly enabled
                    if use_twilio:
                        logger.info(f"Would perform Twilio validation for {e164_format} here if implemented")
                        # In a real implementation, we would call the Twilio validation function here
                        # validation_api = validate_phone_number_twilio(e164_format)
                    else:
                        logger.info(f"Skipping Twilio validation for {e164_format} as requested")
                    
                    found_numbers.append({
                        'original': number_str,
                        'e164': e164_format,
                        'region': region_code if region_code else "Unknown",
                        'priority_region': is_priority,
                        'position': match.start,
                        'validation_api': validation_api
                    })
    except Exception as e:
        logger.error(f"Error during extraction: {e}")
    
    # Sort by position in text
    found_numbers.sort(key=lambda x: x['position'])
    return found_numbers

def main():
    """Test phone extraction on a file with proper Twilio handling."""
    if len(sys.argv) < 2:
        print("Usage: python modified_test.py <file_path> [--use-twilio]")
        return 1
    
    file_path = sys.argv[1]
    use_twilio = "--use-twilio" in sys.argv
    
    print(f"Testing modified phone extraction on file: {file_path}")
    print(f"Twilio validation: {'ENABLED' if use_twilio else 'DISABLED'}")
    
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        
        # Extract phone numbers with proper Twilio handling
        phone_numbers = extract_phone_numbers_modified(text_content, default_region='DE', use_twilio=use_twilio)
        
        # Print results
        print(f"\nFound {len(phone_numbers)} phone numbers:")
        for i, number_info in enumerate(phone_numbers, 1):
            print(f"\n{i}. Original: {number_info['original']}")
            print(f"   E.164 Format: {number_info['e164']}")
            print(f"   Region: {number_info['region']}")
            print(f"   Priority Region: {'Yes' if number_info['priority_region'] else 'No'}")
            print(f"   Position in text: {number_info['position']}")
            
            # Print validation info
            api_status = number_info['validation_api'].get('api_status')
            is_valid = number_info['validation_api'].get('is_valid')
            number_type = number_info['validation_api'].get('type')
            print(f"   API Validation: {api_status}")
            print(f"   Valid: {is_valid}")
            print(f"   Type: {number_type if number_type else 'Not determined'}")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
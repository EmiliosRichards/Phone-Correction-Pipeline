#!/usr/bin/env python3
"""
Simple script to test phone number extraction functionality.
"""
import sys
import os
import logging
from src.phone.extractor import extract_phone_numbers

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Test phone extraction on a single file."""
    if len(sys.argv) < 2:
        print("Usage: python test_phone_extraction.py <file_path> [--use-twilio]")
        return 1
    
    file_path = sys.argv[1]
    use_twilio = "--use-twilio" in sys.argv
    no_twilio = "--no-twilio" in sys.argv
    
    # If --no-twilio is explicitly specified, override use_twilio
    if no_twilio:
        use_twilio = False
    
    print(f"Testing phone extraction on file: {file_path}")
    print(f"Twilio validation: {'ENABLED' if use_twilio else 'DISABLED'}")
    
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        
        # Extract phone numbers
        phone_numbers = extract_phone_numbers(text_content, default_region='DE', use_twilio=use_twilio)
        
        # Print results
        print(f"\nFound {len(phone_numbers)} phone numbers:")
        for i, number_info in enumerate(phone_numbers, 1):
            print(f"\n{i}. Original: {number_info['original']}")
            print(f"   E.164 Format: {number_info['e164']}")
            print(f"   Region: {number_info['region']}")
            print(f"   Priority Region: {'Yes' if number_info['priority_region'] else 'No'}")
            print(f"   Position in text: {number_info['position']}")
            
            # Print validation info if available
            if 'validation_api' in number_info and number_info['validation_api']:
                api_status = number_info['validation_api'].get('api_status')
                is_valid = number_info['validation_api'].get('is_valid')
                number_type = number_info['validation_api'].get('type')
                print(f"   API Validation: {api_status}")
                print(f"   Valid: {is_valid}")
                print(f"   Type: {number_type}")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
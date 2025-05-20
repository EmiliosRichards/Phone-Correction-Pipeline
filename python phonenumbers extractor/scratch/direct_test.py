import sys
import logging
import phonenumbers
from src.phone.extractor import extract_phone_numbers, is_valid_phone_number
from src.text.utils import normalize_text

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_extraction():
    print("Testing phone number extraction...")
    
    # Read the test file
    with open('test_extraction.txt', 'r') as f:
        text = f.read()
    
    print(f"Original text:\n{text}\n")
    
    # Normalize the text
    normalized_text = normalize_text(text)
    print(f"Normalized text:\n{normalized_text}\n")
    
    # Try to parse each number directly to see what happens
    print("Attempting to parse each number directly:")
    test_numbers = [
        "+49 123 456 7890",  # Contains sequential digits "123456789"
        "(030) 12345678",    # Contains sequential digits "12345678"
        "0172-1234567",      # No long sequential pattern
        "+43 1 234567890"    # Contains sequential digits "234567890"
    ]
    
    for num in test_numbers:
        try:
            parsed = phonenumbers.parse(num, "DE")
            is_valid = phonenumbers.is_valid_number(parsed)
            is_possible = phonenumbers.is_possible_number(parsed)
            e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            print(f"Number: {num}")
            print(f"  Parsed: {parsed}")
            print(f"  Valid: {is_valid}")
            print(f"  Possible: {is_possible}")
            print(f"  E164: {e164}")
            print(f"  Our validation: {is_valid_phone_number(num, 'DE')}")
            
            # Check for sequential digits
            from src.phone.extractor import _is_sequential
            national_digits = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
            national_digits = ''.join(c for c in national_digits if c.isdigit())
            print(f"  National digits: {national_digits}")
            print(f"  Has sequential digits: {_is_sequential(national_digits)}")
            print()
        except Exception as e:
            print(f"Number: {num}")
            print(f"  Error: {e}")
            print()
    
    # Extract phone numbers
    phone_numbers = extract_phone_numbers(normalized_text)
    
    # Print results
    print(f"Found {len(phone_numbers)} phone numbers:")
    for number in phone_numbers:
        print(f"- {number}")
    
    return len(phone_numbers)

if __name__ == "__main__":
    count = test_extraction()
    sys.exit(0 if count > 0 else 1)
import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv
from src.utils.logging_config import get_logger

# Load environment variables from .env file if it exists
load_dotenv()

# Get logger for this module
log = get_logger(__name__)

# Get Twilio credentials from environment variables
# Ensure these are set in your environment or a .env file:
# TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Flag to track if Twilio is properly configured
TWILIO_AVAILABLE = False
twilio_client = None

if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    log.warning("Twilio credentials (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) not found in environment variables.")
    log.info("Phone validation will proceed without Twilio API validation.")
else:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        TWILIO_AVAILABLE = True
        log.info("Twilio client initialized successfully.")
    except Exception as e:
        log.error(f"Failed to initialize Twilio client: {e}", exc_info=True)
        log.info("Phone validation will proceed without Twilio API validation.")

def validate_phone_number_twilio(phone_number_e164: str) -> dict:
    """
    Validates a phone number using the Twilio Lookup API V2.

    Args:
        phone_number_e164: The phone number in E.164 format (e.g., +14155552671).

    Returns:
        A dictionary containing validation results:
        {
            "original_number": phone_number_e164,
            "is_valid": bool or None (if API call fails),
            "api_status": str (e.g., "successful", "failed"),
            "error_message": str or None,
            "details": {
                "calling_country_code": str or None,
                "phone_number": str or None, # National format
                "national_format": str or None,
                "country_code": str or None, # ISO country code (e.g., US)
                "type": str or None, # (e.g., mobile, landline, voip)
                "carrier_name": str or None,
                "sim_swap": { ... } or None, # Requires specific package
                "call_forwarding": { ... } or None, # Requires specific package
                "live_activity": { ... } or None, # Requires specific package
                # Add other relevant fields from V2 Lookup as needed
            }
        }
    """
    result = {
        "original_number": phone_number_e164,
        "is_valid": None,
        "api_status": "not_attempted",
        "error_message": None,
        "details": {}
    }

    if not TWILIO_AVAILABLE:
        result["api_status"] = "skipped"
        result["is_valid"] = True  # Assume valid since we can't check with Twilio
        result["error_message"] = "Twilio validation skipped: Twilio client not initialized (check credentials)."
        log.info(f"Twilio validation skipped for {phone_number_e164}: Twilio client not initialized.")
        return result

    if not phone_number_e164 or not phone_number_e164.startswith('+'):
        result["api_status"] = "failed"
        result["is_valid"] = False
        result["error_message"] = "Invalid format: Number must be in E.164 format (e.g., +14155552671)."
        log.warning(f"Invalid format for validation: {phone_number_e164}. Must be E.164.")
        return result

    try:
        log.info(f"Attempting Twilio Lookup V2 for: {phone_number_e164}")
        # Using Lookup V2 API - requires fields parameter
        # Common useful fields: line_type_intelligence, carrier_info
        # For more advanced checks (may incur extra cost): sim_swap, call_forwarding, live_activity
        lookup_fields = ["line_type_intelligence", "carrier_info"]
        phone_info = twilio_client.lookups.v2 \
                                   .phone_numbers(phone_number_e164) \
                                   .fetch(fields=",".join(lookup_fields))

        result["api_status"] = "successful"
        result["is_valid"] = phone_info.valid if hasattr(phone_info, 'valid') else None # V2 uses 'valid' attribute

        details = {
            "calling_country_code": phone_info.calling_country_code if hasattr(phone_info, 'calling_country_code') else None,
            "phone_number": phone_info.phone_number if hasattr(phone_info, 'phone_number') else None, # National format from Twilio
            "national_format": phone_info.national_format if hasattr(phone_info, 'national_format') else None,
            "country_code": phone_info.country_code if hasattr(phone_info, 'country_code') else None,
            "type": None, # Initialize type
            "carrier_name": None, # Initialize carrier
        }

        # Extract Line Type Intelligence if available
        if hasattr(phone_info, 'line_type_intelligence') and phone_info.line_type_intelligence:
            lti = phone_info.line_type_intelligence
            details["type"] = lti.get("type") # e.g., mobile, landline, voip, nonFixedVoip, personal, tollFree, premium, sharedCost, uan, voicemail, unknown
            # You can extract more from lti if needed, e.g., lti.get("error_code")

        # Extract Carrier Info if available
        if hasattr(phone_info, 'carrier_info') and phone_info.carrier_info:
            ci = phone_info.carrier_info
            details["carrier_name"] = ci.get("name")
            # You can extract more from ci if needed, e.g., ci.get("mobile_country_code"), ci.get("mobile_network_code"), ci.get("error_code")

        result["details"] = details

        log.info(f"Validation result for {phone_number_e164}: Valid={result['is_valid']}, Type={details.get('type')}, Carrier={details.get('carrier_name')}")

    except TwilioRestException as e:
        result["api_status"] = "failed"
        # Don't automatically mark as invalid - this is just an API failure, not necessarily an invalid number
        result["is_valid"] = None  # Unknown validity due to API error
        result["error_message"] = f"Twilio API Error: Status={e.status}, Code={e.code}, Message={e.msg}"
        log.error(f"Twilio Lookup failed for {phone_number_e164}: {result['error_message']}")
    except Exception as e:
        result["api_status"] = "failed"
        result["is_valid"] = None  # Unknown validity due to error
        result["error_message"] = f"Unexpected error during validation: {str(e)}"
        log.exception(f"Unexpected error validating {phone_number_e164}:") # Log full traceback

    return result

# Example usage (optional, for testing)
if __name__ == "__main__":
    # Make sure TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are set in your environment
    # Or create a .env file in the project root
    if not TWILIO_AVAILABLE:
        print("Twilio client not initialized. Set environment variables and try again.")
        print("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in your environment or .env file.")
        print("You can copy .env.example to .env and fill in your credentials.")
    else:
        # Replace with a number you want to test (use a real number for actual testing)
        # Using a known Twilio test number that should be valid
        test_number_valid = "+15005550006"
        # Using a known Twilio test number that should be invalid
        test_number_invalid = "+15005550001"
        # Using a number not in E.164 format
        test_number_bad_format = "12345"

        print(f"\n--- Testing Valid Number ({test_number_valid}) ---")
        validation_result_valid = validate_phone_number_twilio(test_number_valid)
        print(validation_result_valid)

        print(f"\n--- Testing Invalid Number ({test_number_invalid}) ---")
        validation_result_invalid = validate_phone_number_twilio(test_number_invalid)
        print(validation_result_invalid)

        print(f"\n--- Testing Bad Format Number ({test_number_bad_format}) ---")
        validation_result_bad = validate_phone_number_twilio(test_number_bad_format)
        print(validation_result_bad)

        # Example of a potentially real number (replace or remove for safety)
        # test_real_number = "+4917612345678" # Example German mobile
        # print(f"\n--- Testing Real Number ({test_real_number}) ---")
        # validation_result_real = validate_phone_number_twilio(test_real_number)
        # print(validation_result_real)
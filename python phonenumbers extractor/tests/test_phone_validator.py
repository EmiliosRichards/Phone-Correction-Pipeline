import pytest
from unittest.mock import MagicMock, patch
from twilio.base.exceptions import TwilioRestException

# Import the function and variables to test
from src.phone.validator import validate_phone_number_twilio, twilio_client as validator_twilio_client, TWILIO_AVAILABLE

# Define mock responses for Twilio Lookup V2 API
# Successful response structure (adapt based on actual V2 fields needed)
MOCK_SUCCESS_RESPONSE_VALID = MagicMock()
MOCK_SUCCESS_RESPONSE_VALID.valid = True
MOCK_SUCCESS_RESPONSE_VALID.calling_country_code = '1'
MOCK_SUCCESS_RESPONSE_VALID.phone_number = '(510) 867-5309' # Example national format from Twilio
MOCK_SUCCESS_RESPONSE_VALID.national_format = '(510) 867-5309'
MOCK_SUCCESS_RESPONSE_VALID.country_code = 'US'
MOCK_SUCCESS_RESPONSE_VALID.line_type_intelligence = {'type': 'mobile', 'error_code': None}
MOCK_SUCCESS_RESPONSE_VALID.carrier_info = {'name': 'Test Carrier', 'type': 'mobile', 'error_code': None, 'mobile_country_code': '310', 'mobile_network_code': '410'}
# Add other fields if your validator uses them

MOCK_SUCCESS_RESPONSE_INVALID_NUMBER = MagicMock()
MOCK_SUCCESS_RESPONSE_INVALID_NUMBER.valid = False # Simulate Twilio saying the number itself is invalid
MOCK_SUCCESS_RESPONSE_INVALID_NUMBER.calling_country_code = None # Often null for invalid numbers
MOCK_SUCCESS_RESPONSE_INVALID_NUMBER.phone_number = None
MOCK_SUCCESS_RESPONSE_INVALID_NUMBER.national_format = None
MOCK_SUCCESS_RESPONSE_INVALID_NUMBER.country_code = None
MOCK_SUCCESS_RESPONSE_INVALID_NUMBER.line_type_intelligence = None # No LTI for invalid number
MOCK_SUCCESS_RESPONSE_INVALID_NUMBER.carrier_info = None # No Carrier info

# Mock TwilioRestException for failure simulation
MOCK_API_ERROR = TwilioRestException(status=404, uri='/Lookups/v2/PhoneNumbers/+123', msg='Resource not found', code=20404)


@pytest.fixture(autouse=True)
def mock_twilio_client(mocker):
    """Fixture to automatically mock the twilio_client used in the validator."""
    # Mock the client instance directly within the validator module
    mock_client = MagicMock()
    mocker.patch('src.phone.validator.twilio_client', mock_client)
    # Ensure the validator thinks the client is initialized and available
    mocker.patch('src.phone.validator.TWILIO_ACCOUNT_SID', 'ACxxxxxxxx MOCKED xxxxxxxxxxxx')
    mocker.patch('src.phone.validator.TWILIO_AUTH_TOKEN', 'xxxxxxxx MOCKED xxxxxxxx')
    mocker.patch('src.phone.validator.TWILIO_AVAILABLE', True)

    return mock_client # Return the mock for specific test adjustments if needed

def test_validate_success_valid_number(mock_twilio_client):
    """Test successful validation for a valid E.164 number."""
    test_number = "+15108675309"
    # Configure the mock client's fetch method to return the success response
    mock_twilio_client.lookups.v2.phone_numbers(test_number).fetch.return_value = MOCK_SUCCESS_RESPONSE_VALID

    result = validate_phone_number_twilio(test_number)

    assert result['original_number'] == test_number
    assert result['api_status'] == 'successful'
    assert result['is_valid'] is True
    assert result['error_message'] is None
    assert result['details']['type'] == 'mobile'
    assert result['details']['carrier_name'] == 'Test Carrier'
    assert result['details']['country_code'] == 'US'
    mock_twilio_client.lookups.v2.phone_numbers(test_number).fetch.assert_called_once_with(fields="line_type_intelligence,carrier_info")

def test_validate_success_invalid_number_from_api(mock_twilio_client):
    """Test successful API call but Twilio reports the number as invalid."""
    test_number = "+15005550001" # Example invalid number
    mock_twilio_client.lookups.v2.phone_numbers(test_number).fetch.return_value = MOCK_SUCCESS_RESPONSE_INVALID_NUMBER

    result = validate_phone_number_twilio(test_number)

    assert result['original_number'] == test_number
    assert result['api_status'] == 'successful'
    assert result['is_valid'] is False # API reported as invalid
    assert result['error_message'] is None
    assert result['details']['type'] is None # No type info expected
    assert result['details']['carrier_name'] is None
    mock_twilio_client.lookups.v2.phone_numbers(test_number).fetch.assert_called_once_with(fields="line_type_intelligence,carrier_info")


def test_validate_api_error(mock_twilio_client):
    """Test handling of a TwilioRestException during API call."""
    test_number = "+1234567890" # Number that causes an error
    # Configure the mock client's fetch method to raise an exception
    mock_twilio_client.lookups.v2.phone_numbers(test_number).fetch.side_effect = MOCK_API_ERROR

    result = validate_phone_number_twilio(test_number)

    assert result['original_number'] == test_number
    assert result['api_status'] == 'failed'
    assert result['is_valid'] is None # API errors now return None instead of False
    assert 'Twilio API Error' in result['error_message']
    assert 'Status=404' in result['error_message']
    assert 'Code=20404' in result['error_message']
    assert result['details'] == {} # No details on error
    mock_twilio_client.lookups.v2.phone_numbers(test_number).fetch.assert_called_once_with(fields="line_type_intelligence,carrier_info")

def test_validate_invalid_format_input(mock_twilio_client):
    """Test validation attempt with a number not in E.164 format."""
    test_number = "1234567890" # Missing '+'

    result = validate_phone_number_twilio(test_number)

    assert result['original_number'] == test_number
    assert result['api_status'] == 'failed'
    assert result['is_valid'] is False
    assert 'Invalid format' in result['error_message']
    assert result['details'] == {}
    # Ensure the API was NOT called for bad format
    mock_twilio_client.lookups.v2.phone_numbers().fetch.assert_not_called()

def test_validate_empty_input(mock_twilio_client):
    """Test validation attempt with empty string."""
    test_number = ""

    result = validate_phone_number_twilio(test_number)

    assert result['original_number'] == test_number
    assert result['api_status'] == 'failed'
    assert result['is_valid'] is False
    assert 'Invalid format' in result['error_message'] # Should fail format check
    assert result['details'] == {}
    mock_twilio_client.lookups.v2.phone_numbers().fetch.assert_not_called()

@patch('src.phone.validator.TWILIO_AVAILABLE', False)
def test_validate_twilio_client_not_initialized():
    """Test behavior when Twilio client failed to initialize (e.g., missing creds)."""
    test_number = "+15108675309"

    result = validate_phone_number_twilio(test_number)

    assert result['original_number'] == test_number
    assert result['api_status'] == 'skipped'
    assert result['is_valid'] is True  # We assume valid when Twilio is not available
    assert 'Twilio validation skipped' in result['error_message']
    assert result['details'] == {}

def test_validate_api_error_handling(mock_twilio_client):
    """Test that API errors don't automatically mark numbers as invalid."""
    test_number = "+1234567890"
    # Configure the mock client's fetch method to raise an exception
    mock_twilio_client.lookups.v2.phone_numbers(test_number).fetch.side_effect = MOCK_API_ERROR

    result = validate_phone_number_twilio(test_number)

    assert result['original_number'] == test_number
    assert result['api_status'] == 'failed'
    assert result['is_valid'] is None  # Should be None, not False
    assert 'Twilio API Error' in result['error_message']
    assert result['details'] == {}
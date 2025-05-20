"""Schema validation utilities for the LLM pipeline."""

from typing import Dict, Any, List, Optional, Set, Union, Tuple # Tuple might already be here
from enum import Enum, auto

class SchemaValidationError(Exception):
    """Custom exception for schema validation errors."""
    pass

class PhoneCategory(str, Enum):
    """Valid categories for phone numbers."""
    SALES = "Sales"
    SUPPORT = "Support"
    RECRUITING = "Recruiting"
    GENERAL = "General"
    LOW_VALUE = "LowValue"

# Required fields for phone number objects
REQUIRED_PHONE_FIELDS = {
    "original_number_text": str,
    "normalized_number": str,
    "category": (str, PhoneCategory),  # Accepts string or PhoneCategory enum
    "confidence": (int, float),
    "context_snippet": str
    # Optional fields like company_name and extra_details are not listed here
    # as this dict defines fields that *must* be present.
}

# Valid phone number categories (kept for backward compatibility)
VALID_CATEGORIES = {category.value for category in PhoneCategory}

def validate_single_phone_number(phone: Dict[str, Any], index: int, valid_categories: Optional[Set[Union[str, PhoneCategory]]] = None, strict: bool = True) -> None:
    """
    Validate a single phone number object.
    
    Args:
        phone: The phone number object to validate
        index: The index of the phone number in the list
        valid_categories: Optional set of valid categories. If None, uses global VALID_CATEGORIES
        strict: If False, skips confidence range validation
        
    Raises:
        SchemaValidationError: If the phone number object is invalid
    """
    if not isinstance(phone, dict):
        raise SchemaValidationError(f"Phone number at index {index} must be a dictionary")
        
    # Check required fields
    for field, field_type in REQUIRED_PHONE_FIELDS.items():
        if field not in phone:
            raise SchemaValidationError(f"Phone number at index {index} missing required field: {field}")
        if not isinstance(phone[field], field_type):
            raise SchemaValidationError(f"Phone number at index {index} field '{field}' has invalid type")
            
    # Validate category
    categories = valid_categories if valid_categories is not None else VALID_CATEGORIES
    category_value = phone["category"].value if isinstance(phone["category"], PhoneCategory) else phone["category"]
    valid_values = {cat.value if isinstance(cat, PhoneCategory) else cat for cat in categories}
    
    if category_value not in valid_values:
        raise SchemaValidationError(f"Phone number at index {index} has invalid category: {category_value}")
        
    # Validate confidence score (only in strict mode)
    if strict and not 0 <= phone["confidence"] <= 1:
        raise SchemaValidationError(f"Phone number at index {index} has invalid confidence score: {phone['confidence']}")

def validate_phone_number_list(phone_numbers: List[Dict[str, Any]], valid_categories: Optional[Set[Union[str, PhoneCategory]]] = None, strict: bool = True) -> None:
    """
    Validate the list of phone numbers.
    
    Args:
        phone_numbers: The list of phone numbers to validate
        valid_categories: Optional set of valid categories. If None, uses global VALID_CATEGORIES
        strict: If False, skips confidence range validation
        
    Raises:
        SchemaValidationError: If the phone numbers list is invalid
    """
    if not isinstance(phone_numbers, list):
        raise SchemaValidationError("'phone_numbers' must be a list")
        
    for i, phone in enumerate(phone_numbers):
        validate_single_phone_number(phone, i, valid_categories, strict)

def validate_metadata(metadata: Dict[str, Any], phone_numbers: List[Dict[str, Any]], strict: bool = True) -> None:
    """
    Validate the metadata object.
    
    Args:
        metadata: The metadata object to validate
        phone_numbers: The list of phone numbers for cross-validation
        strict: If False, skips total_numbers_found validation
        
    Raises:
        SchemaValidationError: If the metadata is invalid
    """
    if not isinstance(metadata, dict):
        raise SchemaValidationError("'metadata' must be a dictionary")
        
    if "total_numbers_found" not in metadata:
        raise SchemaValidationError("Missing 'total_numbers_found' in metadata")
        
    if not isinstance(metadata["total_numbers_found"], int):
        raise SchemaValidationError("'total_numbers_found' must be an integer")
        
    # Only validate total_numbers_found in strict mode
    if strict and metadata["total_numbers_found"] != len(phone_numbers):
        raise SchemaValidationError("'total_numbers_found' doesn't match number of phone numbers")

def validate_output(data: Dict[str, Any], valid_categories: Optional[Set[Union[str, PhoneCategory]]] = None, strict: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate that the output data matches the v2 schema.
    
    This function performs comprehensive validation of the LLM output, including:
    1. Phone number category validation:
       - Validates against predefined categories: Sales, Support, Recruiting, General, LowValue
       - Categories can be provided as either strings or PhoneCategory enum values
       - Custom category sets can be provided via valid_categories parameter
       - Case-sensitive matching is enforced
    
    2. Confidence score validation (in strict mode):
       - Must be a number between 0 and 1 (inclusive)
       - Can be either integer or float
       - Validation skipped in non-strict mode
    
    3. Context validation:
       - Must be a non-empty string
       - Provides surrounding text for the phone number
    
    4. Metadata validation:
       - Requires total_numbers_found field
       - In strict mode, must match actual number of phone numbers found
    
    Args:
        data: The output data to validate
        valid_categories: Optional set of valid categories. If None, uses global VALID_CATEGORIES
        strict: If False, skips total_numbers_found and confidence range validation
        
    Returns:
        A tuple: (is_valid: bool, error_message: Optional[str])
        
    Example:
        >>> data = {
        ...     "phone_numbers": [
        ...         {
        ...             "number": "+1-555-123-4567",
        ...             "category": PhoneCategory.SALES,
        ...             "confidence": 0.95,
        ...             "context": "Contact sales at +1-555-123-4567"
        ...         }
        ...     ],
        ...     "metadata": {
        ...         "total_numbers_found": 1
        ...     }
        ... }
        >>> is_valid, error = validate_output(data)
        >>> is_valid
        True
    """
    try:
        # Check top-level structure
        if not isinstance(data, dict):
            return False, "Output must be a dictionary"
            
        if "phone_numbers" not in data:
            return False, "Missing 'phone_numbers' field"
            
        if "metadata" not in data:
            return False, "Missing 'metadata' field"
        
        # These internal validators will raise SchemaValidationError on failure
        validate_phone_number_list(data["phone_numbers"], valid_categories, strict)
        validate_metadata(data["metadata"], data["phone_numbers"], strict)
            
        return True, None # All validations passed
    except SchemaValidationError as e:
        return False, str(e) # Catch internal validation errors and return them

def validate_strict(data: Dict[str, Any], strict: bool = True) -> bool:
    """
    Wrapper function for validate_output that provides a strict/non-strict validation mode.
    
    In non-strict mode (strict=False), the following validations are skipped:
    - Confidence score range validation (0 <= confidence <= 1)
    - Total numbers found validation (metadata.total_numbers_found == len(phone_numbers))
    
    This is useful for development mode or when working with partial outputs.
    
    Args:
        data: The output data to validate
        strict: If False, skips total_numbers_found and confidence range validation
        
    Returns:
        True if the data is valid
        
    Raises:
        SchemaValidationError: If the data doesn't match the schema
    """
    return validate_output(data, strict=strict) 
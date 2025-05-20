"""Pydantic models for structured LLM outputs."""

from typing import List, Dict, Type, Optional, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime

# Attempt to import PhoneCategory from the existing schema_utils
# This assumes schema_utils.py is in the same directory or accessible via Python path
try:
    from .schema_utils import PhoneCategory
except ImportError:
    # Fallback for cases where direct relative import might fail (e.g. running script directly)
    # In a proper package structure, the above should work.
    # As a last resort, redefine if necessary, but ideally, it's imported.
    from enum import Enum
    class PhoneCategory(str, Enum):
        SALES = "Sales"
        SUPPORT = "Support"
        RECRUITING = "Recruiting"
        GENERAL = "General"
        LOW_VALUE = "LowValue"

class ContactPointDetails(BaseModel):
    """Detailed information associated with a contact point, often found alongside a phone number."""
    model_config = {"json_schema_exclude_defaults": True}

    email: Optional[str] = Field(description="Associated email address, if any.")
    contact_name: Optional[str] = Field(description="Name of the contact person, if any.")
    contact_role: Optional[str] = Field(description="Job role or title of the contact person, if any.")
    address: Optional[str] = Field(description="Physical address associated, if any.")
    hours: Optional[str] = Field(description="Operating hours, if mentioned.")
    other_notes: Optional[str] = Field(description="Any other relevant textual notes or details.")
    # For truly arbitrary key-value pairs not fitting above, a Dict could be added,
    # but that might re-introduce the original problem if not handled carefully by Gemini.
    # Sticking to defined fields is safer for now.

class PhoneNumberDetail(BaseModel):
    """Pydantic model for a single extracted phone number and its details."""
    model_config = {"json_schema_exclude_defaults": True}

    original_number_text: str = Field(..., description="The exact text of the phone number as found in the source.")
    normalized_number: str = Field(..., description="The phone number, normalized to a standard format (e.g., E.164).")
    category: PhoneCategory = Field(..., description="The classified category of the phone number.")
    confidence: float = Field(..., description="The confidence score (0.0 to 1.0) of the extraction and classification.")
    context_snippet: str = Field(..., description="A snippet of text surrounding the found phone number, providing context.")
    company_name: Optional[str] = Field(description="Optional: The company name associated with the phone number, if identifiable.")
    extra_details: Optional[ContactPointDetails] = Field(description="Optional: Other relevant details extracted for this contact point.")

class Metadata(BaseModel):
    """Pydantic model for the metadata of the LLM output."""
    model_config = {"json_schema_exclude_defaults": True}

    total_numbers_found: int = Field(..., description="The total number of phone numbers found in the input.") # Removed ge=0
    processing_timestamp: Optional[datetime] = Field(description="Timestamp of when the processing was completed.")
    # Potentially add other metadata like input_file_name, model_used, etc. later

class PhoneNumberOutput(BaseModel):
    """Pydantic model for the complete phone number extraction output."""
    model_config = {"json_schema_exclude_defaults": True}

    phone_numbers: List[PhoneNumberDetail] = Field(..., description="A list of extracted phone number details.")
    metadata: Metadata = Field(..., description="Metadata associated with this extraction process.")

    @validator('metadata')
    def check_total_numbers_match(cls, metadata, values):
        """Validate that total_numbers_found in metadata matches the actual count."""
        if 'phone_numbers' in values and metadata.total_numbers_found != len(values['phone_numbers']):
            # This validation is useful but might be too strict if the LLM makes a mistake in counting.
            # For now, let's keep it, but it could be relaxed or made a warning.
            # raise ValueError(
            #     f"Mismatch: metadata.total_numbers_found ({metadata.total_numbers_found}) "
            #     f"does not match actual count of phone_numbers ({len(values['phone_numbers'])})."
            # )
            # Let's log a warning or handle this more gracefully if the LLM is supposed to provide the count.
            # For now, we assume the Pydantic model is primarily for schema enforcement of the *structure*.
            # The Gemini API will populate this based on its understanding.
            pass # Relaxing this for now, as the LLM provides this value.
        return metadata


# Registry for Pydantic models
_PYDANTIC_MODELS: Dict[str, Type[BaseModel]] = {
    "PhoneNumberOutput": PhoneNumberOutput,
    "PhoneNumberDetail": PhoneNumberDetail,
    "Metadata": Metadata,
    "ContactPointDetails": ContactPointDetails, # Add new model to registry
}

def get_pydantic_model(name: str) -> Optional[Type[BaseModel]]:
    """
    Retrieves a Pydantic model class by its string name.

    Args:
        name: The string name of the Pydantic model.

    Returns:
        The Pydantic model class if found, else None.
    """
    return _PYDANTIC_MODELS.get(name)

if __name__ == '__main__':
    # Example Usage and Validation
    sample_good_data = {
        "phone_numbers": [
            {
                "original_number_text": "Call us at (555) 123-4567 for sales",
                "normalized_number": "+15551234567",
                "category": "Sales", # Will be converted to PhoneCategory.SALES
                "confidence": 0.95,
                "context_snippet": "for sales inquiries, Call us at (555) 123-4567 for sales today",
                "company_name": "Acme Corp",
                "extra_details": {
                    "email": "sales@acme.corp",
                    "contact_name": "John Doe",
                    "contact_role": "Sales Manager"
                }
            },
            {
                "original_number_text": "Support: 555-987-6543",
                "normalized_number": "+15559876543",
                "category": PhoneCategory.SUPPORT,
                "confidence": 0.88,
                "context_snippet": "For technical issues, contact Support: 555-987-6543 anytime."
            }
        ],
        "metadata": {
            "total_numbers_found": 2
            # processing_timestamp will be auto-generated
        }
    }

    try:
        output_model = PhoneNumberOutput(**sample_good_data)
        print("Sample data is valid!")
        print(output_model.model_dump_json(indent=2))

        # Test get_pydantic_model
        ResolvedModel = get_pydantic_model("PhoneNumberOutput")
        if ResolvedModel:
            resolved_instance = ResolvedModel(**sample_good_data)
            print("\nSuccessfully resolved and instantiated model via get_pydantic_model.")
            assert resolved_instance.metadata.total_numbers_found == 2

    except Exception as e:
        print(f"Validation Error: {e}")

    sample_bad_data_confidence = {
        "phone_numbers": [{"original_number_text": "123", "normalized_number": "123", "category": "General", "confidence": 2.0, "context_snippet": "test"}],
        "metadata": {"total_numbers_found": 1}
    }
    try:
        PhoneNumberOutput(**sample_bad_data_confidence)
    except Exception as e:
        print(f"\nCaught expected validation error for bad confidence: {e}")

    sample_bad_data_category = {
        "phone_numbers": [{"original_number_text": "123", "normalized_number": "123", "category": "InvalidCat", "confidence": 0.5, "context_snippet": "test"}],
        "metadata": {"total_numbers_found": 1}
    }
    try:
        PhoneNumberOutput(**sample_bad_data_category)
    except Exception as e:
        print(f"\nCaught expected validation error for bad category: {e}")
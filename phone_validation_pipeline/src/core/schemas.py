from typing import List, Optional
from pydantic import BaseModel, Field

class PhoneNumberLLMOutput(BaseModel):
    """
    Defines the structure for a single phone number extracted by the LLM.

    This Pydantic model is used to ensure that the LLM's output for each
    identified phone number conforms to a specific schema, including the number
    itself, its perceived type, and a confidence score.

    Attributes:
        number (str): The extracted phone number, ideally normalized to E.164
                      international format (e.g., "+12125551234").
        type (str): The perceived type or context of the phone number as determined
                    by the LLM (e.g., "Main Line", "Sales", "Customer Support", "Fax").
        classification (str): LLM's quality/relevance assessment (e.g., 'Primary',
                              'Secondary', 'Support', 'Low Relevance', 'Non-Business').
        source_url (Optional[str]): The source URL from which the number was originally found.
                                    This field is populated programmatically, not by the LLM.
    """
    number: str = Field(description="The phone number, ideally in E.164 international format.")
    type: str = Field(description="The type or context of the number (e.g., 'Main Line', 'Sales', 'Support', 'Fax').")
    classification: str = Field(description="LLM's quality/relevance assessment (e.g., 'Primary', 'Secondary', 'Support', 'Low Relevance', 'Non-Business').")
    source_url: Optional[str] = Field(default=None, description="The source URL from which the number was originally found.")

class LLMExtractionResult(BaseModel):
    """
    Defines the structure for the overall list of phone numbers extracted by the LLM.

    This Pydantic model is primarily used when the LLM is expected to return a
    JSON object containing a list of phone number details.

    Attributes:
        extracted_numbers (List[PhoneNumberLLMOutput]): A list where each item is an
                                                       instance of `PhoneNumberLLMOutput`,
                                                       representing an extracted phone number.
    """
    extracted_numbers: List[PhoneNumberLLMOutput] = Field(description="A list of phone numbers extracted by the LLM.")
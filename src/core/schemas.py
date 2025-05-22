from typing import List, Optional, Dict, Any
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
        original_input_company_name (Optional[str]): The company name from the original input row
                                                     that led to this number being found via this source_url.
    """
    number: str = Field(description="The phone number, ideally in E.164 international format.")
    type: str = Field(description="The type or context of the number (e.g., 'Main Line', 'Sales', 'Support', 'Fax').")
    classification: str = Field(description="LLM's quality/relevance assessment (e.g., 'Primary', 'Secondary', 'Support', 'Low Relevance', 'Non-Business').")
    source_url: Optional[str] = Field(default=None, description="The source URL from which the number was originally found.")
    original_input_company_name: Optional[str] = Field(default=None, description="Original input company name for this source.")

class MinimalExtractionOutput(BaseModel):
    """
    Defines the structure for the overall list of phone numbers extracted by the LLM,
    representing a minimal enrichment profile (Profile 1).

    This Pydantic model is primarily used when the LLM is expected to return a
    JSON object containing a list of phone number details. It reflects the
    original behavior of extracting phone numbers with minimal enrichment.

    Attributes:
        extracted_numbers (List[PhoneNumberLLMOutput]): A list where each item is an
                                                       instance of `PhoneNumberLLMOutput`,
                                                       representing an extracted phone number.
    """
    extracted_numbers: List[PhoneNumberLLMOutput] = Field(description="A list of phone numbers extracted by the LLM.")

class AdditionalInformation(BaseModel):
    """
    Represents a piece of additional information, potentially tied to a phone number,
    extracted during an enriched profiling process. This supports the 'additional_info'
    field for Profile 2.
    """
    info_type: str = Field(description="Type of information (e.g., 'email', 'name', 'role', 'department', 'location').")
    value: Any = Field(description="The actual information content. Can be a string, list, or dict depending on info_type for flexibility.")
    associated_number: Optional[str] = Field(default=None, description="The phone number (ideally E.164) this information is associated with, if any.")
    source_context: Optional[str] = Field(default=None, description="Brief context or source snippet where this info was found, aiding traceability.")
    confidence: Optional[float] = Field(default=None, ge=0, le=1, description="Confidence score for this specific piece of information, if available.")

class EnrichedExtractionOutput(BaseModel):
    """
    Defines the structure for an enriched extraction output (Profile 2),
    including phone numbers, additional contact details, and potentially a summary.
    This schema is designed with an "LLM assessment-first mindset", providing
    structured and traceable information.
    """
    extracted_numbers: List[PhoneNumberLLMOutput] = Field(description="A list of phone numbers extracted by the LLM, similar to MinimalExtractionOutput.")
    additional_info: Optional[List[AdditionalInformation]] = Field(default_factory=list, description="A list of additional structured information items like emails, names, roles.")
    homepage_summary: Optional[str] = Field(default=None, description="A brief summary of the homepage content, relevant for summarization tasks linked to Profile 2.")
    overall_confidence: Optional[float] = Field(default=None, ge=0, le=1, description="Overall confidence score for the entire enriched extraction process and its output.")
    processing_notes: Optional[List[str]] = Field(default_factory=list, description="Notes generated during the enrichment process (e.g., warnings, steps taken, LLM reasoning snippets).")
    raw_source_text_snippet: Optional[str] = Field(default=None, description="A snippet of the raw text from which the primary information was extracted, for traceability and assessment.")


class ConsolidatedPhoneNumberSource(BaseModel):
    """
    Represents a specific source (page/path and type) for a phone number
    within a single company's website.
    """
    type: str = Field(description="The perceived type of the number from this specific source (e.g., 'Sales', 'Support').")
    source_path: str = Field(description="The path or specific part of the URL where this number type was identified (e.g., '/contact', '/about/locations/berlin').")
    original_full_url: str = Field(description="The original full URL from which this number was extracted.")
    original_input_company_name: Optional[str] = Field(default=None, description="Original input company name associated with this specific source.")

class ConsolidatedPhoneNumber(BaseModel):
    """
    Represents a unique phone number found for a company, along with all its
    identified types and source paths from within the company's website.
    """
    number: str = Field(description="The unique phone number, ideally in E.164 format.")
    classification: str = Field(description="The overall classification for this number (e.g., 'Primary', 'Secondary'). This might be determined by the highest priority classification found across its sources.")
    sources: List[ConsolidatedPhoneNumberSource] = Field(description="A list of sources (type and path) for this number.")

class CompanyContactDetails(BaseModel):
    """
    Represents all consolidated and de-duplicated contact phone numbers
    for a single company, grouped by their canonical base URL.
    """
    company_name: Optional[str] = Field(default=None, description="The name of the company.")
    canonical_base_url: str = Field(description="The canonical base URL for the company (e.g., 'http://example.com').")
    consolidated_numbers: List[ConsolidatedPhoneNumber] = Field(description="A list of unique phone numbers with their aggregated sources.")
    original_input_urls: List[str] = Field(default_factory=list, description="List of all original input URLs that resolved to this canonical base URL.")

class PipelineOutputData(BaseModel):
    """
    Represents the final structured output of the phone extraction and validation pipeline for a single input entry.
    This model is intended for the "flattened" report where we select top contacts.
    """
    run_id: str = Field(description="The unique ID for this processing run.")
    company_name: Optional[str] = Field(default=None, description="Original company name from input.")
    given_url: str = Field(description="Original URL provided in the input.")
    # This will now be the canonical base URL after consolidation
    processed_url: str = Field(description="The canonical base URL after processing and consolidation.")
    
    original_given_phone: Optional[str] = Field(default=None, description="Original phone number from input, if any.")
    normalized_given_phone: Optional[str] = Field(default=None, description="Normalized version of the original input phone, if any.")
    original_number_status: str = Field(default="Pending", description="Status of the original input phone number (e.g., 'Verified', 'Invalid', 'Not Provided').")

    overall_verification_status: str = Field(default="Pending", description="Overall status for the company's contact data retrieval (e.g., 'Contacts Found', 'No Contacts Found', 'Scraping Failed').")

    # Fields for top selected contacts
    primary_number_1: Optional[str] = Field(default=None)
    primary_type_1: Optional[str] = Field(default=None) # This could be a concatenation of types if a number serves multiple primary roles
    primary_source_urls_1: Optional[List[str]] = Field(default=None) # List of original full URLs for this number

    secondary_number_1: Optional[str] = Field(default=None)
    secondary_type_1: Optional[str] = Field(default=None)
    secondary_source_urls_1: Optional[List[str]] = Field(default=None)

    secondary_number_2: Optional[str] = Field(default=None)
    secondary_type_2: Optional[str] = Field(default=None)
    secondary_source_urls_2: Optional[List[str]] = Field(default=None)

    # To store all found numbers in a structured way, if needed beyond the top N.
    # This links to the new consolidation model.
    all_company_contacts: Optional[CompanyContactDetails] = Field(default=None, description="All consolidated contact details for the company from the processed URL.")
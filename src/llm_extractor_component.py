import logging
import json
import re
import os
from typing import Dict, Any, List, Tuple, Optional

from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel
from google.generativeai.types import GenerationConfig
from google.api_core import exceptions as google_exceptions
from pydantic import ValidationError as PydanticValidationError

import phonenumbers
from phonenumbers import PhoneNumberFormat

# Assuming schemas are in core.schemas and config in core.config
from .core.schemas import PhoneNumberLLMOutput, LLMExtractionResult
from .core.config import AppConfig

logger = logging.getLogger(__name__)

class GeminiLLMExtractor:
    """
    A component responsible for extracting phone numbers from text using the
    Google Gemini Large Language Model (LLM).

    This class handles loading prompt templates, interacting with the Gemini API
    to get structured JSON output (conforming to `PhoneNumberLLMOutput` schema),
    and normalizing the extracted phone numbers.
    """

    def __init__(self, config: AppConfig):
        """
        Initializes the GeminiLLMExtractor with necessary configurations.

        Args:
            config (AppConfig): An instance of `AppConfig` containing settings
                                such as the Gemini API key, model name, temperature,
                                max tokens, and paths for prompt templates.

        Raises:
            ValueError: If `GEMINI_API_KEY` is not found in the provided configuration.
        """
        self.config = config
        if not self.config.gemini_api_key:
            logger.error("GEMINI_API_KEY not provided in configuration.")
            raise ValueError("GEMINI_API_KEY not found in configuration.")
        
        configure(api_key=self.config.gemini_api_key)
        
        self.model = GenerativeModel(
            self.config.llm_model_name,
            # generation_config is set per-request to include response_schema
        )
        logger.info(f"GeminiLLMExtractor initialized with model: {self.config.llm_model_name}")

    def _load_prompt_template(self, prompt_file_path: str) -> str:
        """
        Loads a prompt template from the specified file path.

        Args:
            prompt_file_path (str): The absolute or relative path to the prompt
                                    template file.

        Returns:
            str: The content of the prompt template file as a string.

        Raises:
            FileNotFoundError: If the prompt template file cannot be found.
            Exception: For other errors encountered during file reading.
        """
        try:
            # Ensure path is absolute or correctly relative to where config expects it
            # AppConfig.llm_prompt_template_path is relative to project root.
            # If prompt_file_path is passed directly, ensure it's resolvable.
            # For now, assume prompt_file_path is correctly resolved by the caller.
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Prompt template file not found: {prompt_file_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading prompt template file {prompt_file_path}: {e}")
            raise

    def _normalize_phone_number(self, number_str: str, country_codes: List[str]) -> Optional[str]:
        """
        Normalizes a given phone number string to E.164 format.

        It attempts to parse the number using each of the provided `country_codes`
        as a region hint. If unsuccessful, it falls back to using the
        `self.config.default_region_code`.

        Args:
            number_str (str): The phone number string to normalize.
            country_codes (List[str]): A list of ISO 3166-1 alpha-2 country codes
                                       (e.g., ["US", "DE"]) to use as hints for parsing.

        Returns:
            Optional[str]: The normalized phone number in E.164 format if successful,
                           otherwise None.
        """
        if not number_str or not isinstance(number_str, str):
            return None

        for country_code in country_codes: # Iterate through preferred country codes
            try:
                parsed_num = phonenumbers.parse(number_str, region=country_code.upper())
                if phonenumbers.is_valid_number(parsed_num):
                    return phonenumbers.format_number(parsed_num, PhoneNumberFormat.E164)
            except phonenumbers.NumberParseException:
                # Log lightly, as this is expected for some numbers/regions
                logger.debug(f"Could not parse '{number_str}' with region '{country_code}'.")
                continue # Try next country code
        
        # Fallback if not parsed with specific country codes, try with default_region_code
        if self.config.default_region_code:
            try:
                parsed_num = phonenumbers.parse(number_str, region=self.config.default_region_code.upper())
                if phonenumbers.is_valid_number(parsed_num):
                    logger.debug(f"Normalized '{number_str}' to E.164 using default region '{self.config.default_region_code}'.")
                    return phonenumbers.format_number(parsed_num, PhoneNumberFormat.E164)
            except phonenumbers.NumberParseException:
                logger.warning(f"Could not parse phone number '{number_str}' even with default region '{self.config.default_region_code}'.")
        
        logger.warning(f"Could not normalize phone number '{number_str}' to E.164 with hints {country_codes} or default region.")
        return None
    def _extract_json_from_text(self, text_output: Optional[str]) -> Optional[str]:
        """
        Extracts a JSON string from a larger text block, potentially cleaning
        markdown code fences.

        Args:
            text_output (Optional[str]): The raw text output from the LLM.

        Returns:
            Optional[str]: The extracted JSON string, or None if not found or input is invalid.
        """
        if not text_output:
            return None

        # Regex to find content within ```json ... ``` or ``` ... ```,
        # or a standalone JSON object/array.
        # It tries to capture the content inside the innermost curly braces or square brackets.
        # This is a best-effort extraction.
        match = re.search(
            r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```|(\{.*\}|\[.*\])",
            text_output,
            re.DOTALL # DOTALL allows . to match newlines
        )

        if match:
            # Prioritize the content within backticks if both groups match
            # (e.g. ```json { "key": "value" } ```)
            # Group 1 is for content within ```json ... ``` or ``` ... ```
            # Group 2 is for standalone JSON object/array
            json_str = match.group(1) or match.group(2)
            if json_str:
                return json_str.strip()
        
        logger.debug(f"No clear JSON block found in LLM text output: {text_output[:200]}...")
        return None

    def extract_phone_numbers(
        self,
        candidate_items: List[Dict[str, str]], # Changed input
        prompt_template_path: str,
        llm_context_dir: str,  # New parameter
        file_identifier_prefix: str  # New parameter
    ) -> Tuple[List[PhoneNumberLLMOutput], Optional[str]]:
        """
        Classifies candidate phone numbers based on their snippets and source URLs using the Gemini API.

        The method loads a prompt template, formats it with the list of candidate items (each
        containing a number, its snippet, and source URL), and sends it to the Gemini model.
        It expects a JSON response conforming to LLMExtractionResult, which contains a list
        of PhoneNumberLLMOutput objects (now with a 'classification' field).

        Args:
            candidate_items (List[Dict[str, str]]): A list of dictionaries, where each
                                                   dictionary contains "candidate_number",
                                                   "snippet", and "source_url".
            prompt_template_path (str): The file path to the prompt template. The template
                                        should expect a JSON list of these candidate items.
            llm_context_dir (str): The directory path to save LLM context files.
            file_identifier_prefix (str): A prefix for naming LLM context files (e.g., "CANONICAL_domain_com").

        Returns:
            Tuple[List[PhoneNumberLLMOutput], Optional[str]]:
            A tuple where the first element is a list of `PhoneNumberLLMOutput`
            objects (each potentially containing a normalized phone number and
            its context/confidence). The second element is a string containing
            the raw JSON response from the LLM, or an error message string if
            an error occurred. The list of `PhoneNumberLLMOutput` objects will
            be empty if no numbers are found or if an error prevents extraction.

        Raises:
            Catches and logs various exceptions including `FileNotFoundError` for
            the prompt, `google_exceptions.GoogleAPIError` for API issues,
            `json.JSONDecodeError`, and `PydanticValidationError`.
        """
        raw_llm_response_str: Optional[str] = None
        extracted_numbers: List[PhoneNumberLLMOutput] = []

        try:
            prompt_template = self._load_prompt_template(prompt_template_path)
            # Serialize candidate_items to a JSON string
            candidate_items_json_str = json.dumps(candidate_items, indent=2)
            # The new prompt template expects "[Insert JSON list of (candidate_number, source_url, snippet) objects here]"
            formatted_prompt = prompt_template.replace(
                "[Insert JSON list of (candidate_number, source_url, snippet) objects here]",
                candidate_items_json_str
            )

            # Save the full prompt
            # Define filename and path before the try block to ensure filepath is bound for error logging
            full_prompt_filename = f"{file_identifier_prefix}_llm_full_prompt.txt"
            full_prompt_filepath = os.path.join(llm_context_dir, full_prompt_filename)
            try:
                with open(full_prompt_filepath, 'w', encoding='utf-8') as f_prompt:
                    f_prompt.write(formatted_prompt)
                logger.info(f"Saved full LLM prompt to {full_prompt_filepath}")
            except IOError as e_io:
                logger.error(f"IOError saving full LLM prompt to {full_prompt_filepath}: {e_io}")
            # Continue even if saving prompt fails, as main functionality is LLM call

        except Exception as e:
            logger.error(f"Failed to load or format prompt: {e}")
            return [], f"Error loading prompt: {str(e)}"

        generation_config = GenerationConfig(
            candidate_count=1,
            max_output_tokens=self.config.llm_max_tokens,
            temperature=self.config.llm_temperature
        )

        try:
            logger.debug(f"Sending request to Gemini. Prompt starts with: {formatted_prompt[:200]}...")
            response = self.model.generate_content(
                formatted_prompt,
                generation_config=generation_config
            )
            
            # Gemini SDK should parse into List[PhoneNumberLLMOutput] if response_schema is List[PydanticModel]
            # and response_mime_type is "application/json".
            # The raw text is in response.text if needed for saving.
            
            raw_llm_response_str = response.text # Save the raw text response
            
            if not response.candidates:
                logger.error("No candidates found in Gemini response.")
                return [], json.dumps({"error": "No candidates in response", "raw_response_text": raw_llm_response_str})

            # Accessing parsed Pydantic objects:
            # If response_schema=List[PhoneNumberLLMOutput] was successful,
            # response.candidates[0].content.parts[0].function_call.args might contain the data
            # or more directly, if the SDK handles it well, response.parsed might exist.
            # Let's check response.text first for the raw string, then try to parse it if response.parsed isn't directly usable.

            parsed_objects: Optional[List[PhoneNumberLLMOutput]] = None
            
            # The Gemini SDK documentation suggests that if `response_schema` is provided,
            # the `response.text` will be the JSON string, and `response.candidates[0].content.parts[0]`
            # might not be a function call but directly the structured content.
            # The `response.parsed` attribute is the most direct way if the SDK version supports it well.

            # For now, let's assume response.text contains the JSON list as per Gemini's capability
            # and we parse it with Pydantic. If Gemini directly populates response.parsed with List[PhoneNumberLLMOutput],
            # that would be even better.
            # The `google-generativeai` library for Gemini, when `response_schema` is used,
            # should ideally make the parsed objects available directly.
            # If `response.text` is a JSON string representing a list of `PhoneNumberLLMOutput` objects:
            
            if raw_llm_response_str:
                json_candidate_str = self._extract_json_from_text(raw_llm_response_str)
                if json_candidate_str:
                    logger.debug(f"Attempting to parse extracted JSON candidate: {json_candidate_str[:200]}...")
                    try:
                        parsed_json_object = json.loads(json_candidate_str)
                        # Validate the entire object against LLMExtractionResult
                        llm_result = LLMExtractionResult(**parsed_json_object) # Pydantic validation here
                        
                        validated_numbers = llm_result.extracted_numbers

                        # Create a mapping from input candidate_number to its source_url
                        # The candidate_items are available in the outer scope of this method.
                        # candidate_items: List[Dict[str, str]], where each dict has "number", "source_url", "snippet"
                        source_url_map = {
                            item['number']: item['source_url']
                            for item in candidate_items
                        }

                        # Populate source_url and re-normalize phone numbers
                        for llm_output in validated_numbers:
                            # Populate source_url
                            # llm_output.number should already be E.164 normalized by the LLM or earlier regex stage.
                            # If not, this matching might be less reliable.
                            # Assuming llm_output.number is the key to find in source_url_map.
                            # The input candidate_number to LLM is already E.164.
                            # The LLM is asked to return the original E.164 number.
                            # The post-LLM normalization step also ensures it's E.164.
                            original_candidate_number = llm_output.number # This is the number LLM returned
                            llm_output.source_url = source_url_map.get(original_candidate_number)
                            if not llm_output.source_url:
                                logger.warning(f"Could not find source_url for LLM output number: {original_candidate_number}. Map keys: {list(source_url_map.keys())[:5]}")
                            
                            # Re-normalize phone numbers (existing logic)
                            if llm_output.number: # Number might be None if LLM fails for an entry
                                normalized_num = self._normalize_phone_number(llm_output.number, self.config.target_country_codes)
                                if normalized_num:
                                    llm_output.number = normalized_num
                                else:
                                    logger.warning(f"LLM extracted number '{llm_output.number}' could not be normalized to E.164. Keeping as is or consider filtering.")
                                    # Decide if unnormalizable numbers should be kept or discarded. For now, keeping.
                        extracted_numbers = validated_numbers
                        logger.info(f"Successfully extracted and validated {len(extracted_numbers)} phone numbers from LLM.")

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON from extracted candidate: {e}. Candidate: '{json_candidate_str}'. Raw LLM: '{raw_llm_response_str[:500]}...'")
                        return [], json.dumps({
                            "error": "Failed to parse LLM JSON response from extracted candidate",
                            "extracted_candidate": json_candidate_str,
                            "raw_response_text": raw_llm_response_str,
                            "details": str(e)
                        })
                    except PydanticValidationError as ve:
                        logger.error(f"Pydantic validation failed for parsed JSON: {ve}. Parsed JSON: '{json_candidate_str}'. Raw LLM: '{raw_llm_response_str[:500]}...'")
                        return [], json.dumps({
                            "error": "Pydantic validation failed for parsed LLM response",
                            "parsed_json": json_candidate_str,
                            "raw_response_text": raw_llm_response_str,
                            "details": ve.errors()
                        })
                else: # if not json_candidate_str
                    logger.warning(f"Could not extract a JSON block from LLM response. Raw response: {raw_llm_response_str[:500]}...")
                    return [], json.dumps({
                        "error": "Could not extract JSON block from LLM response",
                        "raw_response_text": raw_llm_response_str
                    })
            else: # if not raw_llm_response_str (empty response from LLM)
                logger.warning("Gemini response text is empty.")
                finish_reason = "Unknown"
                if response and response.candidates and response.candidates[0].finish_reason: # Check response obj
                    finish_reason = response.candidates[0].finish_reason.name
                logger.warning(f"Gemini finish reason: {finish_reason}")
                if finish_reason != "STOP":
                    return [], json.dumps({
                        "error": f"Gemini generation stopped due to: {finish_reason}",
                        "raw_response_text": raw_llm_response_str
                    })
                return [], json.dumps({
                    "error": "Empty text from LLM response",
                    "raw_response_text": raw_llm_response_str
                })


        except google_exceptions.GoogleAPIError as e:
            logger.error(f"Gemini API error: {e}")
            # Consider specific error types for retry if LLMBaseClient's logic isn't used.
            # For now, just return the error.
            raw_llm_response_str = json.dumps({"error": f"Gemini API error: {str(e)}", "type": type(e).__name__})
            return [], raw_llm_response_str
        except Exception as e:
            logger.error(f"Unexpected error during LLM extraction: {e}", exc_info=True)
            raw_llm_response_str = json.dumps({"error": f"Unexpected error: {str(e)}", "type": type(e).__name__})
            return [], raw_llm_response_str
        
        # Ensure raw_llm_response_str is a string for the second part of the tuple
        if raw_llm_response_str is None:
            raw_llm_response_str = json.dumps({"error": "LLM response was not captured."})
            
        return extracted_numbers, raw_llm_response_str
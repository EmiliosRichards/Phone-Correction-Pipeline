import logging
import json
import re
import os
from typing import Dict, Any, List, Tuple, Optional

from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel
from google.generativeai.types import GenerationConfig
from google.api_core import exceptions as google_exceptions
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import ValidationError as PydanticValidationError

import phonenumbers
from phonenumbers import PhoneNumberFormat

# Assuming schemas are in core.schemas and config in core.config
from .core.schemas import PhoneNumberLLMOutput, MinimalExtractionOutput
from .core.config import AppConfig

logger = logging.getLogger(__name__)

RETRYABLE_GEMINI_EXCEPTIONS = (
    google_exceptions.DeadlineExceeded,
    google_exceptions.ServiceUnavailable,
    google_exceptions.ResourceExhausted,  # For rate limits
    google_exceptions.InternalServerError, # 500 errors
    google_exceptions.Aborted
    # google_exceptions.Unavailable # Removed as it's not a known attribute, ServiceUnavailable covers the intent
)

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
                logger.info(f"Could not parse phone number '{number_str}' even with default region '{self.config.default_region_code}'.")
        
        logger.info(f"Could not normalize phone number '{number_str}' to E.164 with hints {country_codes} or default region.")
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

    @retry(
        stop=stop_after_attempt(3),  # Try 3 times in total (1 initial + 2 retries)
        wait=wait_exponential(multiplier=1, min=2, max=10),  # Wait 2s, then 4s (max 10s)
        retry=retry_if_exception_type(RETRYABLE_GEMINI_EXCEPTIONS),
        reraise=True  # Reraise the exception if all retries fail
    )
    def _generate_content_with_retry(self, formatted_prompt: str, generation_config: GenerationConfig, file_identifier_prefix: str, triggering_input_row_id: Any, triggering_company_name: str):
        """
        Internal method to call Gemini API with retry logic.
        """
        logger.info(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Attempting to generate content with Gemini API...")
        response = self.model.generate_content(
            formatted_prompt,
            generation_config=generation_config
        )
        # Basic check for safety, though specific non-retriable content blocks
        # would ideally be handled by the caller if they are not exceptions.
        if response and response.prompt_feedback and response.prompt_feedback.block_reason:
            logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Gemini content generation blocked. Reason: {response.prompt_feedback.block_reason.name}. This might not be retriable by network retries.")
            # Depending on the block_reason, one might choose to raise a specific non-retryable error here.
            # For now, we let it proceed and the caller handles the content.

        logger.info(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Successfully generated content from Gemini API attempt.")
        return response

    def _process_successful_llm_item(
        self,
        llm_output: PhoneNumberLLMOutput,
        input_item_details: Dict[str, Any]
    ) -> PhoneNumberLLMOutput:
        """Enriches and normalizes a successfully matched LLM output item."""
        llm_output.source_url = input_item_details.get('source_url')
        llm_output.original_input_company_name = input_item_details.get('original_input_company_name')

        if llm_output.number:
            normalized_num = self._normalize_phone_number(llm_output.number, self.config.target_country_codes)
            if normalized_num:
                llm_output.number = normalized_num
            else:
                logger.warning(f"LLM output number '{llm_output.number}' (from input '{input_item_details.get('number')}') could not be normalized. Keeping as is.")
        return llm_output

    def _create_error_llm_item(
        self,
        input_item_details: Dict[str, Any],
        error_type_str: str = "Error_ProcessingFailed",
        classification_str: str = "Non-Business",
        file_identifier_prefix: Optional[str] = "N/A", # Added
        triggering_input_row_id: Optional[Any] = "N/A", # Added
        triggering_company_name: Optional[str] = "N/A" # Added
    ) -> PhoneNumberLLMOutput:
        """Creates a PhoneNumberLLMOutput for an item that failed processing."""
        logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Creating error item for input number '{input_item_details.get('number')}' from source '{input_item_details.get('source_url', 'Unknown Source')}' due to: {error_type_str}")
        return PhoneNumberLLMOutput(
            number=str(input_item_details.get('number')), # Use the original input number
            type=error_type_str,
            classification=classification_str,
            source_url=input_item_details.get('source_url'),
            original_input_company_name=input_item_details.get('original_input_company_name')
            # snippet is not part of PhoneNumberLLMOutput, it's input context
            # confidence and other fields will use Pydantic defaults (e.g., None)
        )

    def extract_phone_numbers(
        self,
        candidate_items: List[Dict[str, str]], # Changed input
        prompt_template_path: str,
        llm_context_dir: str,  # New parameter
        file_identifier_prefix: str,  # New parameter
        triggering_input_row_id: Any,
        triggering_company_name: str
    ) -> Tuple[List[PhoneNumberLLMOutput], Optional[str], Optional[Dict[str, int]]]:
        """
        Classifies candidate phone numbers based on their snippets and source URLs using the Gemini API.

        The method loads a prompt template, formats it with the list of candidate items (each
        containing a number, its snippet, and source URL), and sends it to the Gemini model.
        It expects a JSON response conforming to LLMExtractionResult, which contains a list
        of PhoneNumberLLMOutput objects (now with a 'classification' field).

        Args:
            candidate_items (List[Dict[str, str]]): A list of dictionaries, where each
                                                   dictionary contains "candidate_number",
                                                   "snippet", "source_url", and "original_input_company_name".
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
        final_processed_outputs: List[Optional[PhoneNumberLLMOutput]] = [None] * len(candidate_items)
        items_needing_retry: List[Tuple[int, Dict[str, Any]]] = [] # Stores (original_index, input_item_dict)
        raw_llm_response_str_initial: Optional[str] = None
        token_usage_stats_initial: Optional[Dict[str, int]] = None
        # To accumulate token stats from multiple calls
        accumulated_token_stats: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


        # --- BEGIN NEW LOGIC FOR SAVING TEMPLATE ONCE ---
        try:
            run_output_dir = os.path.dirname(llm_context_dir)
            if not run_output_dir: # e.g. if llm_context_dir was just "llm_context"
                logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Could not determine run_output_dir from llm_context_dir: '{llm_context_dir}'. Cannot save prompt template.")
            else:
                # Ensure the parent directory for llm_prompt_template.txt exists
                os.makedirs(run_output_dir, exist_ok=True)

                template_output_filename = "llm_prompt_template.txt"
                template_output_filepath = os.path.join(run_output_dir, template_output_filename)

                if not os.path.exists(template_output_filepath):
                    logger.info(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Attempting to save base LLM prompt template to {template_output_filepath}")
                    try:
                        # Load the original base prompt template content
                        base_prompt_content = self._load_prompt_template(prompt_template_path)
                        with open(template_output_filepath, 'w', encoding='utf-8') as f_template:
                            f_template.write(base_prompt_content)
                        logger.info(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Successfully saved base LLM prompt template to {template_output_filepath}")
                    except FileNotFoundError:
                        # _load_prompt_template logs this. This log is for context of this specific save operation.
                        logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Base prompt template file '{prompt_template_path}' not found. Cannot save a copy to '{template_output_filepath}'.")
                    except IOError as e_io:
                        logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] IOError saving base LLM prompt template to '{template_output_filepath}': {e_io}")
                    except Exception as e_template_save: # Catch any other error during template loading/saving
                        logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Unexpected error during saving of base LLM prompt template to '{template_output_filepath}': {e_template_save}")
                else:
                    logger.debug(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Base LLM prompt template '{template_output_filepath}' already exists. Skipping save.")
        except Exception as e_path_setup: # Catch errors from os.path.dirname or os.makedirs
            logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Error in pre-processing for saving prompt template (e.g., path manipulation for '{llm_context_dir}'): {e_path_setup}")
        # --- END NEW LOGIC FOR SAVING TEMPLATE ONCE ---

        # --- Initial LLM Call ---
        current_items_for_llm_call = list(candidate_items) # Make a mutable copy
        
        try:
            prompt_template_pass1 = self._load_prompt_template(prompt_template_path)
            candidate_items_json_str_pass1 = json.dumps(current_items_for_llm_call, indent=2)
            formatted_prompt_pass1 = prompt_template_pass1.replace(
                "[Insert JSON list of (candidate_number, source_url, snippet) objects here]",
                candidate_items_json_str_pass1
            )
        except Exception as e:
            logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Failed to load or format prompt for initial call: {e}")
            # Populate all with error items
            for i, item_detail in enumerate(candidate_items):
                final_processed_outputs[i] = self._create_error_llm_item(item_detail, "Error_PromptLoading", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
            return [item for item in final_processed_outputs if item is not None], f"Error loading prompt: {str(e)}", accumulated_token_stats

        generation_config_pass1 = GenerationConfig(
            candidate_count=1,
            max_output_tokens=self.config.llm_max_tokens,
            temperature=self.config.llm_temperature
        )

        try:
            logger.debug(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Sending initial request to Gemini for {len(current_items_for_llm_call)} items. Prompt starts with: {formatted_prompt_pass1[:200]}...")
            response_pass1 = self._generate_content_with_retry(formatted_prompt_pass1, generation_config_pass1, file_identifier_prefix, triggering_input_row_id, triggering_company_name)
            raw_llm_response_str_initial = response_pass1.text

            if hasattr(response_pass1, 'usage_metadata') and response_pass1.usage_metadata:
                token_usage_stats_initial = {
                    "prompt_tokens": response_pass1.usage_metadata.prompt_token_count,
                    "completion_tokens": response_pass1.usage_metadata.candidates_token_count,
                    "total_tokens": response_pass1.usage_metadata.total_token_count
                }
                for key in accumulated_token_stats: accumulated_token_stats[key] += token_usage_stats_initial.get(key, 0)
                logger.info(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Initial LLM call usage: {token_usage_stats_initial}")
            else:
                logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Initial LLM call: Gemini API usage metadata not found.")

            if not response_pass1.candidates:
                logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] No candidates found in initial Gemini response.")
                for i, item_detail in enumerate(candidate_items):
                    final_processed_outputs[i] = self._create_error_llm_item(item_detail, "Error_NoLLMCandidates", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
                return [item for item in final_processed_outputs if item is not None], json.dumps({"error": "No candidates in initial response", "raw_response_text": raw_llm_response_str_initial}), accumulated_token_stats

            if raw_llm_response_str_initial:
                json_candidate_str_pass1 = self._extract_json_from_text(raw_llm_response_str_initial)
                if json_candidate_str_pass1:
                    try:
                        parsed_json_object_pass1 = json.loads(json_candidate_str_pass1)
                        llm_result_pass1 = MinimalExtractionOutput(**parsed_json_object_pass1)
                        validated_numbers_pass1 = llm_result_pass1.extracted_numbers

                        if len(validated_numbers_pass1) != len(current_items_for_llm_call):
                            logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Initial LLM call: Mismatch in item count. Input: {len(current_items_for_llm_call)}, Output: {len(validated_numbers_pass1)}. Cannot reliably map. Marking all as error.")
                            for i, item_detail in enumerate(candidate_items):
                                final_processed_outputs[i] = self._create_error_llm_item(item_detail, "Error_LLMItemCountMismatch", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
                            return [item for item in final_processed_outputs if item is not None], raw_llm_response_str_initial, accumulated_token_stats
                        
                        for i, input_item_detail in enumerate(current_items_for_llm_call):
                            llm_output_item = validated_numbers_pass1[i]
                            if llm_output_item.number == input_item_detail['number']:
                                final_processed_outputs[i] = self._process_successful_llm_item(llm_output_item, input_item_detail)
                            else:
                                logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}, ItemCompany: {input_item_detail.get('original_input_company_name')}] Initial mismatch for input '{input_item_detail['number']}', LLM returned '{llm_output_item.number}'. Queueing for retry.")
                                items_needing_retry.append((i, input_item_detail))
                    
                    except json.JSONDecodeError as e:
                        logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Initial LLM call: Failed to parse JSON: {e}. Raw: '{raw_llm_response_str_initial[:500]}...'")
                        for i, item_detail in enumerate(candidate_items): final_processed_outputs[i] = self._create_error_llm_item(item_detail, "Error_InitialJsonParse", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
                        return [item for item in final_processed_outputs if item is not None], raw_llm_response_str_initial, accumulated_token_stats
                    except PydanticValidationError as ve:
                        logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Initial LLM call: Pydantic validation failed: {ve}. Raw: '{raw_llm_response_str_initial[:500]}...'")
                        for i, item_detail in enumerate(candidate_items): final_processed_outputs[i] = self._create_error_llm_item(item_detail, "Error_InitialPydanticValidation", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
                        return [item for item in final_processed_outputs if item is not None], raw_llm_response_str_initial, accumulated_token_stats
                else: # No JSON block
                    logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Initial LLM call: Could not extract JSON block. Raw: {raw_llm_response_str_initial[:500]}...")
                    for i, item_detail in enumerate(candidate_items): final_processed_outputs[i] = self._create_error_llm_item(item_detail, "Error_InitialNoJsonBlock", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
                    return [item for item in final_processed_outputs if item is not None], raw_llm_response_str_initial, accumulated_token_stats
            else: # Empty response
                logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Initial LLM call: Response text is empty.")
                for i, item_detail in enumerate(candidate_items): final_processed_outputs[i] = self._create_error_llm_item(item_detail, "Error_InitialEmptyResponse", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
                return [item for item in final_processed_outputs if item is not None], raw_llm_response_str_initial, accumulated_token_stats

        except google_exceptions.GoogleAPIError as e:
            logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Initial LLM call: Gemini API error: {e}")
            for i, item_detail in enumerate(candidate_items): final_processed_outputs[i] = self._create_error_llm_item(item_detail, f"Error_InitialApiError_{type(e).__name__}", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
            return [item for item in final_processed_outputs if item is not None], json.dumps({"error": f"Initial Gemini API error: {str(e)}", "type": type(e).__name__}), accumulated_token_stats
        except Exception as e:
            logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Initial LLM call: Unexpected error: {e}", exc_info=True)
            for i, item_detail in enumerate(candidate_items): final_processed_outputs[i] = self._create_error_llm_item(item_detail, f"Error_InitialUnexpected_{type(e).__name__}", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
            return [item for item in final_processed_outputs if item is not None], json.dumps({"error": f"Initial unexpected error: {str(e)}", "type": type(e).__name__}), accumulated_token_stats

        # --- Iterative Retry Loop for Mismatched Items ---
        current_retry_attempt = 0
        raw_llm_response_str_retry: Optional[str] = None # To store the last retry response

        while items_needing_retry and current_retry_attempt < self.config.llm_max_retries_on_number_mismatch:
            current_retry_attempt += 1
            logger.info(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Attempting LLM retry pass #{current_retry_attempt} for {len(items_needing_retry)} mismatched items.")
            
            inputs_for_this_retry_pass = [item_tuple[1] for item_tuple in items_needing_retry]
            original_indices_for_this_pass = [item_tuple[0] for item_tuple in items_needing_retry]
            
            try:
                prompt_template_retry = self._load_prompt_template(prompt_template_path) # Reload, though it's same
                candidate_items_json_str_retry = json.dumps(inputs_for_this_retry_pass, indent=2)
                formatted_prompt_retry = prompt_template_retry.replace(
                    "[Insert JSON list of (candidate_number, source_url, snippet) objects here]",
                    candidate_items_json_str_retry
                )
            except Exception as e:
                logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Failed to load or format prompt for retry pass #{current_retry_attempt}: {e}")
                # Mark remaining items_needing_retry as error and break loop
                for original_idx, item_detail_retry in items_needing_retry:
                    if final_processed_outputs[original_idx] is None: # Only if not already processed
                         final_processed_outputs[original_idx] = self._create_error_llm_item(item_detail_retry, f"Error_RetryPromptLoading_Pass{current_retry_attempt}", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
                items_needing_retry.clear() # Stop further retries
                break

            generation_config_retry = GenerationConfig( # Same config as initial
                candidate_count=1, max_output_tokens=self.config.llm_max_tokens, temperature=self.config.llm_temperature
            )

            try:
                logger.debug(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Sending retry #{current_retry_attempt} request to Gemini for {len(inputs_for_this_retry_pass)} items.")
                response_retry = self._generate_content_with_retry(formatted_prompt_retry, generation_config_retry, file_identifier_prefix, triggering_input_row_id, triggering_company_name)
                raw_llm_response_str_retry = response_retry.text # Store this retry's raw response

                if hasattr(response_retry, 'usage_metadata') and response_retry.usage_metadata:
                    token_stats_retry = {
                        "prompt_tokens": response_retry.usage_metadata.prompt_token_count,
                        "completion_tokens": response_retry.usage_metadata.candidates_token_count,
                        "total_tokens": response_retry.usage_metadata.total_token_count
                    }
                    for key in accumulated_token_stats: accumulated_token_stats[key] += token_stats_retry.get(key, 0)
                    logger.info(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] LLM retry #{current_retry_attempt} usage: {token_stats_retry}")
                else:
                    logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] LLM retry #{current_retry_attempt}: Gemini API usage metadata not found.")

                still_mismatched_after_this_retry: List[Tuple[int, Dict[str, Any]]] = []
                if not response_retry.candidates:
                    logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Retry #{current_retry_attempt}: No candidates in Gemini response. All items in this batch remain mismatched.")
                    still_mismatched_after_this_retry.extend(items_needing_retry) # All failed this retry
                elif raw_llm_response_str_retry:
                    json_candidate_str_retry = self._extract_json_from_text(raw_llm_response_str_retry)
                    if json_candidate_str_retry:
                        try:
                            parsed_json_object_retry = json.loads(json_candidate_str_retry)
                            llm_result_retry = MinimalExtractionOutput(**parsed_json_object_retry)
                            validated_numbers_retry = llm_result_retry.extracted_numbers

                            if len(validated_numbers_retry) != len(inputs_for_this_retry_pass):
                                logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Retry #{current_retry_attempt}: Mismatch in item count. Input: {len(inputs_for_this_retry_pass)}, Output: {len(validated_numbers_retry)}. All items in this batch remain mismatched.")
                                still_mismatched_after_this_retry.extend(items_needing_retry)
                            else:
                                for j, retried_input_item_detail in enumerate(inputs_for_this_retry_pass):
                                    original_input_idx = original_indices_for_this_pass[j]
                                    retried_llm_output_item = validated_numbers_retry[j]

                                    if retried_llm_output_item.number == retried_input_item_detail['number']:
                                        logger.info(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}, ItemCompany: {retried_input_item_detail.get('original_input_company_name')}] Retry pass #{current_retry_attempt} successful for input '{retried_input_item_detail['number']}'.")
                                        final_processed_outputs[original_input_idx] = self._process_successful_llm_item(retried_llm_output_item, retried_input_item_detail)
                                    else:
                                        logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}, ItemCompany: {retried_input_item_detail.get('original_input_company_name')}] Mismatch persists after retry pass #{current_retry_attempt} for input '{retried_input_item_detail['number']}', LLM returned '{retried_llm_output_item.number}'.")
                                        still_mismatched_after_this_retry.append((original_input_idx, retried_input_item_detail))
                        
                        except json.JSONDecodeError as e:
                            logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Retry #{current_retry_attempt}: Failed to parse JSON: {e}. All items in this batch remain mismatched.")
                            still_mismatched_after_this_retry.extend(items_needing_retry)
                        except PydanticValidationError as ve:
                            logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Retry #{current_retry_attempt}: Pydantic validation failed: {ve}. All items in this batch remain mismatched.")
                            still_mismatched_after_this_retry.extend(items_needing_retry)
                    else: # No JSON block in retry
                        logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Retry #{current_retry_attempt}: Could not extract JSON block. All items in this batch remain mismatched.")
                        still_mismatched_after_this_retry.extend(items_needing_retry)
                else: # Empty response in retry
                    logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Retry #{current_retry_attempt}: Response text is empty. All items in this batch remain mismatched.")
                    still_mismatched_after_this_retry.extend(items_needing_retry)
                
                items_needing_retry = still_mismatched_after_this_retry

            except google_exceptions.GoogleAPIError as e:
                logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Retry #{current_retry_attempt}: Gemini API error: {e}. All items in this batch remain mismatched for this attempt.")
                # No change to items_needing_retry, they will be processed in next attempt or final error handling
                # We don't clear items_needing_retry here, to allow further retries if configured.
            except Exception as e:
                logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] Retry #{current_retry_attempt}: Unexpected error: {e}", exc_info=True)
                # As above, items remain for next attempt or final error handling.

        # --- Handle Persistently Mismatched Items (after all retries) ---
        if items_needing_retry:
            logger.warning(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] {len(items_needing_retry)} items still mismatched after all {self.config.llm_max_retries_on_number_mismatch} retries.")
            for original_idx, item_detail_persist_error in items_needing_retry:
                if final_processed_outputs[original_idx] is None: # Only if not somehow processed
                    final_processed_outputs[original_idx] = self._create_error_llm_item(item_detail_persist_error, "Error_PersistentMismatchAfterRetries", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
        
        # --- Handle Initial Mismatches if Retries were Disabled (max_retries = 0) ---
        # This case is covered if items_needing_retry was populated and loop didn't run.
        # The previous block "Handle Persistently Mismatched Items" will catch them if max_retries was 0.

        # --- Final check for any None slots (e.g. if an error occurred before first pass processing for an item) ---
        for i, output_item in enumerate(final_processed_outputs):
            if output_item is None:
                logger.error(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}, ItemCompany: {candidate_items[i].get('original_input_company_name')}] Item at original index {i} (input: {candidate_items[i].get('number')}) was not processed. Creating error item.")
                final_processed_outputs[i] = self._create_error_llm_item(candidate_items[i], "Error_NotProcessed", file_identifier_prefix=file_identifier_prefix, triggering_input_row_id=triggering_input_row_id, triggering_company_name=triggering_company_name)
        
        # The primary raw response to return is from the initial call, or the last retry if that's more relevant.
        response_origin_log_message = ""
        if raw_llm_response_str_initial is not None and (raw_llm_response_str_retry is None or items_needing_retry or not current_retry_attempt): # Prefer initial if no retries or retries didn't change outcome for all
            response_origin_log_message = "Using raw response from initial LLM call."
            final_raw_llm_response_str = raw_llm_response_str_initial
        elif raw_llm_response_str_retry is not None:
            response_origin_log_message = f"Using raw response from last LLM retry attempt ({current_retry_attempt})."
            final_raw_llm_response_str = raw_llm_response_str_retry
        else: # Neither initial nor retry had a response text (e.g. API error before text, or prompt loading error)
            response_origin_log_message = "Using default/error JSON as final raw response (no text from LLM)."
            final_raw_llm_response_str = json.dumps({"error": "LLM response was not captured or was empty."})
        
        logger.info(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] {response_origin_log_message}")


        # Cast List[Optional[PhoneNumberLLMOutput]] to List[PhoneNumberLLMOutput]
        # All None should have been filled by error items.
        processed_results: List[PhoneNumberLLMOutput] = [item for item in final_processed_outputs if item is not None]
        
        # Log summary of processed items
        successful_items_count = sum(1 for item in processed_results if item and not item.type.startswith("Error_"))
        error_items_count = len(processed_results) - successful_items_count
        logger.info(f"[{file_identifier_prefix}, RowID: {triggering_input_row_id}, Company: {triggering_company_name}] LLM extraction summary: {successful_items_count} successful, {error_items_count} errors out of {len(candidate_items)} candidates.")

        return processed_results, final_raw_llm_response_str, accumulated_token_stats
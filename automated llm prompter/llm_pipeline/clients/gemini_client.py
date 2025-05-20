import logging
import json
from typing import Dict, Any, Type
from datetime import datetime

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel as PydanticBaseModel, ValidationError as PydanticValidationError

from llm_pipeline.common.llm_client_base_v2 import LLMBaseClientV2 # Updated import
from llm_pipeline.common.metrics import MetricsLogger # For type hinting
from llm_pipeline.common.pydantic_schemas import get_pydantic_model

logger = logging.getLogger(__name__)

class GeminiAPIClient(LLMBaseClientV2): # Updated base class
    """
    Client for interacting with the Google Gemini API.
    """

    def __init__(self, client_config: Dict[str, Any], metrics_logger: MetricsLogger = None):
        """
        Initializes the GeminiAPIClient.

        Args:
            client_config: Configuration dictionary for the client.
                           Expected keys: "api_key", "model_name" (optional),
                           "temperature" (optional), "max_tokens" (optional).
            metrics_logger: Optional logger for metrics.
        """
        super().__init__(client_config, metrics_logger)

        api_key = self.client_config.get("api_key")
        if not api_key:
            raise ValueError("Gemini API key not found in client_config. "
                             "Ensure it's loaded, e.g., from an environment variable.")
        genai.configure(api_key=api_key)

        model_name = self.client_config.get("model_name", "gemini-1.5-pro-latest")
        self.model = genai.GenerativeModel(model_name)

        logger.info(f"GeminiAPIClient initialized with model: {model_name}")

    def _prepare_request(self, prompt_content: str, input_text: str, **kwargs) -> str:
        """
        Formats the prompt_content template with the input_text.

        Args:
            prompt_content: The prompt template string.
            input_text: The text to be inserted into the prompt.
            **kwargs: Additional keyword arguments (not used by this basic implementation).

        Returns:
            The fully formatted prompt string.
        """
        # The 'prompt_content' argument is assumed to have been primarily formatted
        # by LLMBaseClientV2._format_prompt (e.g., {input_text} replaced).
        # For the Gemini API, the "prepared request" is simply this string.
        # The 'input_text' param is still passed by the base class but typically
        # not re-used here if the base _format_prompt handled it.
        # Additional client-specific formatting could be done here if needed.
        return prompt_content

    def _execute_request(self, payload: str, **kwargs) -> genai.types.GenerateContentResponse:
        """
        Executes the request to the Gemini API.

        Args:
            payload: The formatted prompt string.
            **kwargs: Additional keyword arguments for generation config.

        Returns:
            The response object from the Gemini API.
        """
        try:
            max_tokens = self.client_config.get("max_tokens", 2048)
            temperature = self.client_config.get("temperature", 0.7)
            top_p = self.client_config.get("top_p") # Optional
            top_k = self.client_config.get("top_k") # Optional

            generation_config_params = {
                "candidate_count": 1,
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            }
            if top_p is not None:
                generation_config_params["top_p"] = top_p
            if top_k is not None:
                generation_config_params["top_k"] = top_k

            # Check for Pydantic schema configuration
            pydantic_model_class = None
            pydantic_schema_name = self.client_config.get("pydantic_schema_name")
            if pydantic_schema_name:
                pydantic_model_class = get_pydantic_model(pydantic_schema_name)
                if pydantic_model_class:
                    generation_config_params["response_mime_type"] = "application/json"
                    generation_config_params["response_schema"] = pydantic_model_class # Pass the class directly
                    logger.info(f"Using Pydantic model class directly for Gemini schema: {pydantic_schema_name} ({pydantic_model_class.__name__})")
                else:
                    logger.warning(
                        f"Pydantic schema name '{pydantic_schema_name}' provided in config, "
                        f"but no corresponding model found. Proceeding without schema enforcement."
                    )
            
            generation_config = genai.types.GenerationConfig(**generation_config_params)

            logger.debug(f"Executing Gemini request with payload: {payload[:200]}... "
                         f"and generation_config: {generation_config_params}")
            response = self.model.generate_content(payload, generation_config=generation_config)
            # Store the model class used, if any, for _parse_response to potentially use.
            # This helps _parse_response know if a schema was intended, even if it has to parse text.
            kwargs["pydantic_model_class_used"] = pydantic_model_class
            return response
        except google_exceptions.GoogleAPIError as e:
            logger.error(f"Gemini API error: {e}")
            # Re-raise to be handled by LLMBaseClient's retry mechanism or caller
            raise
        except Exception as e:
            logger.error(f"Unexpected error executing Gemini request: {e}")
            raise # Re-raise

    def _parse_response(self, response: genai.types.GenerateContentResponse, **kwargs) -> Dict[str, Any]:
        """
        Parses the Gemini API response to extract structured JSON.

        Args:
            response: The response object from the Gemini API.
            **kwargs: Additional keyword arguments.

        Returns:
            A dictionary parsed from the JSON response, or an error dictionary.
        """
        try:
            pydantic_model_class: Type[PydanticBaseModel] | None = kwargs.get("pydantic_model_class_used")

            if not response.candidates:
                logger.error("No candidates found in Gemini response.")
                return {"error": "No candidates in response", "raw_response": str(response)}

            first_candidate = response.candidates[0]

            # Attempt to use response.parsed if a Pydantic schema was intended
            if pydantic_model_class and hasattr(first_candidate, 'content') and hasattr(response, 'parsed') and response.parsed is not None:
                try:
                    # Gemini SDK populates response.parsed with instantiated Pydantic objects
                    # if response_schema was used in GenerationConfig.
                    if isinstance(response.parsed, pydantic_model_class):
                        logger.info(f"Successfully parsed Gemini response using Pydantic model via response.parsed: {pydantic_model_class.__name__}")
                        parsed_data = response.parsed.model_dump()
                        if "metadata" in parsed_data and isinstance(parsed_data["metadata"], dict) and \
                           parsed_data["metadata"].get("processing_timestamp") is None:
                            parsed_data["metadata"]["processing_timestamp"] = datetime.now().isoformat()
                        return parsed_data
                    # Handle if the schema was for a list of models, e.g. list[Recipe]
                    # For PhoneNumberOutput, it's a single object, so this might not be hit unless schema changes.
                    # This path is less likely for PhoneNumberOutput which is a single object schema.
                    elif isinstance(response.parsed, list) and \
                         all(isinstance(item, pydantic_model_class) for item in response.parsed):
                        logger.info(f"Successfully parsed Gemini response as list of Pydantic models via response.parsed: {pydantic_model_class.__name__}")
                        # Assuming if it's a list, it's not our main PhoneNumberOutput structure,
                        # so timestamp handling might differ or not apply here.
                        # This case needs review if list[PhoneNumberOutput] becomes a pattern.
                        return [item.model_dump() for item in response.parsed]
                    else:
                        logger.warning(
                            f"Gemini response.parsed type ({type(response.parsed)}) did not directly match "
                            f"expected Pydantic model ({pydantic_model_class.__name__}). Will attempt to parse from text."
                        )
                except PydanticValidationError as ve:
                    logger.warning(f"Pydantic validation failed for response.parsed: {ve}. Will attempt to parse from text.")
                except Exception as e:
                    logger.warning(f"Error processing Gemini response.parsed with Pydantic model {pydantic_model_class.__name__}: {e}. Will attempt to parse from text.")
            
            # Fallback to text parsing (or primary path if no Pydantic schema from response.parsed)
            if not first_candidate.content or not first_candidate.content.parts:
                logger.error("No content parts found in Gemini response candidate.")
                return {"error": "No content parts in candidate", "raw_response": str(response)}

            extracted_text = "".join(part.text for part in first_candidate.content.parts if hasattr(part, 'text'))

            if not extracted_text:
                logger.warning("Extracted text from Gemini response is empty.")
                finish_reason = getattr(first_candidate, 'finish_reason', None)
                if finish_reason and finish_reason.name != "STOP":
                    logger.warning(f"Gemini response finish reason: {finish_reason.name}")
                    return {"error": f"Gemini generation stopped due to: {finish_reason.name}", "raw_response": ""}
                return {"error": "Empty text from LLM response", "raw_response": ""}

            logger.debug(f"Raw text from Gemini: {extracted_text[:500]}...")

            # Strip markdown code block fences
            if extracted_text.strip().startswith("```json"):
                extracted_text = extracted_text.strip()[7:-3] if extracted_text.strip().endswith("```") else extracted_text.strip()[7:]
            elif extracted_text.strip().startswith("```"):
                extracted_text = extracted_text.strip()[3:-3] if extracted_text.strip().endswith("```") else extracted_text.strip()[3:]
            extracted_text = extracted_text.strip()

            try:
                parsed_json_from_llm = json.loads(extracted_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from Gemini text: {e}. Raw text: '{extracted_text}'")
                return {"error": "Failed to parse LLM JSON response from text", "raw_response": extracted_text}

            # If a Pydantic model was intended, validate the parsed JSON with it
            if pydantic_model_class:
                try:
                    validated_output = pydantic_model_class(**parsed_json_from_llm)
                    logger.info(f"Successfully validated parsed text with Pydantic model: {pydantic_model_class.__name__}")
                    parsed_data = validated_output.model_dump()
                    if "metadata" in parsed_data and isinstance(parsed_data["metadata"], dict) and \
                       parsed_data["metadata"].get("processing_timestamp") is None:
                        parsed_data["metadata"]["processing_timestamp"] = datetime.now().isoformat()
                    return parsed_data
                except PydanticValidationError as ve:
                    logger.error(f"Parsed JSON from text failed Pydantic validation for {pydantic_model_class.__name__}: {ve}. Raw JSON: {json.dumps(parsed_json_from_llm, indent=2)}")
                    return {"error": f"Pydantic validation failed for {pydantic_model_class.__name__}",
                            "raw_response": extracted_text,
                            "validation_errors": ve.errors()} # Pydantic errors() gives structured info
                except Exception as e: # Catch other errors during Pydantic instantiation
                    logger.error(f"Error instantiating Pydantic model {pydantic_model_class.__name__} from parsed JSON: {e}")
                    return {"error": f"Could not instantiate Pydantic model {pydantic_model_class.__name__}", "raw_response": extracted_text}
            
            # Original logic if no Pydantic schema was involved
            logger.debug("No Pydantic schema used or fallback to original parsing logic.")
            if isinstance(parsed_json_from_llm, list):
                return {
                    "phone_numbers": parsed_json_from_llm,
                    "metadata": {
                        "total_numbers_found": len(parsed_json_from_llm),
                        "processing_timestamp": datetime.now().isoformat()
                    }
                }
            elif isinstance(parsed_json_from_llm, dict) and "phone_numbers" in parsed_json_from_llm and "metadata" in parsed_json_from_llm:
                if "processing_timestamp" not in parsed_json_from_llm["metadata"]:
                    parsed_json_from_llm["metadata"]["processing_timestamp"] = datetime.now().isoformat()
                return parsed_json_from_llm
            else:
                logger.error(f"LLM output (no Pydantic) was valid JSON but not the expected structure. Output: {parsed_json_from_llm}")
                return {"error": "LLM JSON output (no Pydantic) is not the expected structure", "raw_response": extracted_text, "parsed_llm_output": parsed_json_from_llm}

        except AttributeError as e:
            # This can happen if the response structure is not as expected
            logger.error(f"Error accessing Gemini response attributes: {e}. Response: {str(response)}")
            return {"error": "Unexpected Gemini response structure", "raw_response": str(response)}
        except Exception as e:
            logger.error(f"Unexpected error parsing Gemini response: {e}")
            # It's useful to know what the raw response was if parsing fails unexpectedly
            raw_text_for_error = "Could not retrieve"
            try:
                raw_text_for_error = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
            except: # pylint: disable=bare-except
                pass # Keep default "Could not retrieve"
            return {"error": f"Generic error parsing response: {str(e)}", "raw_response": raw_text_for_error}


    def _get_default_config(self) -> Dict[str, Any]:
        """
        Returns default configuration parameters specific to Gemini.
        Currently, most configs are expected via client_config.
        """
        return {
            # Example: "safety_settings": { ... } if needed and not part of profile
        }

    def _get_retry_error_codes(self) -> list[int]:
        """
        Returns a list of HTTP status codes that should be retried.
        For Gemini, specific gRPC or API core exceptions might be more relevant
        than HTTP status codes if not using a direct HTTP endpoint that LLMBaseClient checks.
        LLMBaseClient handles generic exceptions, this is for specific HTTP codes.
        The Gemini client uses google-api-core which has its own retry mechanisms for
        certain errors, but we can specify ones for LLMBaseClient too.
        Common retryable HTTP codes: 429 (Too Many Requests), 500 (Internal Server Error),
        502 (Bad Gateway), 503 (Service Unavailable), 504 (Gateway Timeout).
        """
        return [429, 500, 502, 503, 504]

    def _should_retry_exception(self, exc: Exception) -> bool:
        """
        Determines if an exception from _execute_request should be retried.
        """
        if isinstance(exc, (google_exceptions.DeadlineExceeded,
                            google_exceptions.ServiceUnavailable,
                            google_exceptions.TooManyRequests, # Corresponds to 429
                            google_exceptions.InternalServerError, # Corresponds to 500
                            google_exceptions.Unknown)): # General catch-all for unknown Google API errors
            logger.warning(f"Identified retryable Google API exception: {type(exc).__name__}")
            return True
        return super()._should_retry_exception(exc)
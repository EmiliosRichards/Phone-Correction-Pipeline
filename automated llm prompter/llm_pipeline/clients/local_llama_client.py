import json
import logging
import requests
from typing import Dict, Any

from llm_pipeline.common.llm_client_base_v2 import LLMBaseClientV2 # Updated import
from llm_pipeline.common.metrics import MetricsLogger # For type hinting
import llm_pipeline.config as config # To access DEFAULT_TIMEOUT

class LocalLlamaClient(LLMBaseClientV2): # Updated base class
    """
    Client for interacting with a locally running Llama instance (e.g., via an Ollama-compatible API).
    """

    def __init__(self, client_config: Dict[str, Any], metrics_logger: MetricsLogger = None):
        """
        Initializes the LocalLlamaClient.

        Args:
            client_config: Configuration dictionary for the client.
                           Expected keys: "api_url", "model_name".
                           Optional keys: "temperature", "max_tokens", "timeout".
            metrics_logger: Optional logger for metrics.
        """
        super().__init__(client_config, metrics_logger)
        self.api_url = self.client_config.get("api_url")
        if not self.api_url:
            raise ValueError("Missing 'api_url' in client_config for LocalLlamaClient.")
        self.logger = logging.getLogger(__name__) # Initialize logger

    def _prepare_request(self, prompt_content: str, input_text: str, **kwargs) -> Dict[str, Any]:
        """
        Prepares the JSON payload for the local Llama API.

        Args:
            prompt_content: The prompt template string.
            input_text: The input text to format into the prompt.
            **kwargs: Additional keyword arguments.

        Returns:
            A dictionary representing the JSON payload for the API request.
        """
        formatted_prompt = prompt_content.format(webpage_text=input_text)
        
        payload = {
            "model": self.client_config.get("model_name"),
            "prompt": formatted_prompt,
            "stream": False,  # Important for a single, complete response
            "options": {
                "temperature": self.client_config.get("temperature", 0.7),
            }
        }
        if "max_tokens" in self.client_config:  # Ollama uses num_predict
            payload["options"]["num_predict"] = self.client_config["max_tokens"]
        
        # Add other Ollama-specific options from client_config if needed
        # For example, if client_config contains an "ollama_options" dictionary:
        # if "ollama_options" in self.client_config and isinstance(self.client_config["ollama_options"], dict):
        #     payload["options"].update(self.client_config["ollama_options"])
            
        return payload

    def _execute_request(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Executes the HTTP POST request to the local Llama API.

        Args:
            payload: The JSON payload from _prepare_request.
            **kwargs: Additional keyword arguments.

        Returns:
            The parsed JSON dictionary from the HTTP response.

        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        try:
            timeout = self.client_config.get("timeout", config.DEFAULT_TIMEOUT)
            self.logger.debug(f"Executing LocalLlama request to {self.api_url} with payload: {payload}")
            http_response = requests.post(self.api_url, json=payload, timeout=timeout)
            http_response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
            return http_response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Local Llama API request to {self.api_url} failed: {e}")
            raise

    def _parse_response(self, response_payload_json: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Parses the JSON response from the Llama API to extract the LLM's output.
        The LLM is expected to return a JSON string, which is then parsed here.

        Args:
            response_payload_json: The direct JSON dictionary from _execute_request.
            **kwargs: Additional keyword arguments.

        Returns:
            A dictionary parsed from the LLM's generated JSON string.
            Returns an error dictionary if parsing fails.

        Raises:
            ValueError: If the LLM's text response is not found in the API output.
        """
        llm_generated_text = response_payload_json.get("response")
        
        if llm_generated_text is None or not llm_generated_text.strip():
            self.logger.error(f"LLM text response not found or empty in API output. Full API response: {response_payload_json}")
            raise ValueError("LLM text response not found or empty in API output.")

        try:
            # Strip potential markdown code block fences
            if llm_generated_text.startswith("```json"):
                llm_generated_text = llm_generated_text[7:]
            if llm_generated_text.endswith("```"):
                llm_generated_text = llm_generated_text[:-3]
            llm_generated_text = llm_generated_text.strip()

            parsed_json_output = json.loads(llm_generated_text)
            return parsed_json_output
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM JSON output: {e}. Raw text from LLM: '{llm_generated_text}'")
            # Return an error structure or raise a specific exception
            return {"error": "Failed to parse LLM JSON response", "raw_response_from_llm": llm_generated_text}

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Returns the default configuration for the LocalLlamaClient.
        """
        return {}
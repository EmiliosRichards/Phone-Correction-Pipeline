import abc
import logging
import time
from typing import Any, Dict, Tuple
from datetime import datetime

from llm_pipeline import config
from llm_pipeline.common.metrics import MetricsLogger, APICallMetrics


class LLMBaseClientV2(abc.ABC): # Renamed class
    """Abstract base class for LLM clients (V2)."""

    def __init__(self, client_config: Dict[str, Any], metrics_logger: MetricsLogger = None):
        self.client_config = client_config
        self.metrics_logger = metrics_logger
        self.logger = logging.getLogger(self.__class__.__name__)

    @abc.abstractmethod
    def _prepare_request(self, prompt_content: str, input_text: str, **kwargs) -> Any:
        pass

    @abc.abstractmethod
    def _execute_request(self, payload: Any, **kwargs) -> Any:
        pass

    @abc.abstractmethod
    def _parse_response(self, response: Any, **kwargs) -> Dict[str, Any]:
        pass

    @abc.abstractmethod
    def _get_default_config(self) -> Dict[str, Any]:
        pass

    def _format_prompt(self, prompt_template: str, input_text: str, **kwargs) -> str:
        """
        Formats the prompt template by replacing the primary input placeholder '{input_text}'.
        Other placeholders using {key} format within the prompt (e.g., in JSON examples)
        should be escaped by doubling the braces (e.g., {{key}}) if .format() were to be used
        more broadly. However, for simplicity and to avoid issues with unescaped braces in
        examples, we will stick to a direct .replace() for the main input.
        
        The **kwargs are not used in this simplified version but kept for signature consistency.
        """
        # Directly replace only the intended placeholder.
        # If "{input_text}" is not found, the original template is returned, which is acceptable.
        if "{input_text}" not in prompt_template:
            self.logger.warning(
                "The placeholder '{input_text}' was not found in the provided prompt_template. "
                "The input_text will be appended to the prompt_template. "
                "Ensure your prompt template is designed accordingly or includes '{input_text}'."
            )
            return f"{prompt_template}\n\n{input_text}"
            
        return prompt_template.replace("{input_text}", input_text)

    def generate(self, prompt_content: str, input_text: str, **kwargs) -> Tuple[Dict[str, Any], Any]:
        formatted_prompt = self._format_prompt(prompt_content, input_text, **kwargs.get("prompt_format_args", {}))
        
        self.logger.debug(f"Formatted prompt (first 500 chars): {formatted_prompt[:500]}...")
        
        retries = 0
        last_exception = None
        prompt_identifier = kwargs.get("prompt_identifier", prompt_content[:50] + "...")
        model_name = self.client_config.get("model_name", "unknown_model")

        while retries < config.MAX_RETRIES:
            try:
                payload = self._prepare_request(formatted_prompt, input_text, **kwargs)
                api_call_start_time = None
                api_call_end_time = None
                raw_response = None
                status_bool = False
                current_exception_message = None

                try:
                    if self.metrics_logger:
                        api_call_start_time = time.perf_counter()
                    raw_response = self._execute_request(payload, **kwargs)
                    if self.metrics_logger:
                        api_call_end_time = time.perf_counter()
                    status_bool = True
                except Exception as e_exec:
                    current_exception_message = str(e_exec)
                    if self.metrics_logger and api_call_start_time is not None:
                        api_call_end_time = time.perf_counter()
                    raise
                finally:
                    if self.metrics_logger and api_call_start_time is not None:
                        latency_ms = (api_call_end_time - api_call_start_time) * 1000 if api_call_end_time is not None else -1
                        input_tokens_val = kwargs.get("input_tokens_count", None)
                        output_tokens_val = kwargs.get("output_tokens_count", None)
                        error_msg_for_log = current_exception_message if not status_bool else None
                        metrics_data = APICallMetrics(
                            timestamp=datetime.now().isoformat(),
                            api_type=self.client_config.get("type", "unknown_provider"),
                            prompt_length=len(str(payload)) if payload else 0,
                            response_length=len(str(raw_response)) if raw_response else 0,
                            total_duration=latency_ms,
                            success=status_bool,
                            error_message=error_msg_for_log,
                            prompt_identifier=prompt_identifier,
                            model_name=model_name,
                            input_tokens=input_tokens_val,
                            output_tokens=output_tokens_val
                        )
                        self.metrics_logger.log_api_call(metrics=metrics_data)
                
                parsed_data = self._parse_response(raw_response, **kwargs)
                self.logger.info(f"LLM generation successful for prompt: {prompt_identifier}")
                return parsed_data, raw_response
            except Exception as e:
                last_exception = e
                self.logger.error(
                    f"LLM generation attempt {retries + 1}/{config.MAX_RETRIES} failed for prompt: {prompt_identifier}. Error: {e}"
                )
                retries += 1
                if retries < config.MAX_RETRIES:
                    time.sleep(2 ** retries) 
                else:
                    self.logger.error(
                        f"LLM generation failed after {config.MAX_RETRIES} retries for prompt: {prompt_identifier}."
                    )
                    raise RuntimeError(
                        f"LLM generation failed after {config.MAX_RETRIES} retries for prompt '{prompt_identifier}'. Last error: {last_exception}"
                    ) from last_exception
        
        self.logger.error(f"LLM generation failed for prompt: {prompt_identifier} (exhausted retries or MAX_RETRIES not positive).")
        raise RuntimeError(f"LLM generation failed for prompt '{prompt_identifier}'. Last error: {last_exception}")
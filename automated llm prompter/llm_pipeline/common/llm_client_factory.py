from typing import Any, Dict, Type

from llm_pipeline.common.llm_client_base_v2 import LLMBaseClientV2 # Updated import
from llm_pipeline.common.metrics import MetricsLogger
from llm_pipeline.clients.gemini_client import GeminiAPIClient
from llm_pipeline.clients.local_llama_client import LocalLlamaClient
from llm_pipeline.clients.ssh_mixtral_client import SSHMixtralClient


# LLM Client Factory
class LLMClientFactory:
    """Factory class for creating LLM clients."""

    _client_map: Dict[str, Type[LLMBaseClientV2]] = { # Updated type hint
        "gemini": GeminiAPIClient,
        "ssh_mixtral": SSHMixtralClient,
        "local_llama": LocalLlamaClient,
        # Actual client classes will be registered here later
    }

    @classmethod
    def register_client(cls, client_type: str, client_class: Type[LLMBaseClientV2]): # Updated type hint
        """Registers a new client type."""
        if not issubclass(client_class, LLMBaseClientV2): # Updated check
            raise TypeError(f"Client class {client_class.__name__} must inherit from LLMBaseClientV2.")
        cls._client_map[client_type.lower()] = client_class
        # Potentially log registration
        # logging.getLogger(__name__).info(f"Registered LLM client type '{client_type}' with class {client_class.__name__}.")


    @classmethod
    def create_client(cls, client_config: Dict[str, Any], metrics_logger: MetricsLogger = None) -> LLMBaseClientV2: # Updated return type hint
        """
        Creates an LLM client instance based on the provided configuration.

        Args:
            client_config: Configuration dictionary for the client.
                           Must contain a "type" key specifying the client type.
            metrics_logger: Optional MetricsLogger instance.

        Returns:
            An instance of an LLMBaseClient subclass.

        Raises:
            ValueError: If the client type is unsupported or missing.
        """
        client_type = client_config.get("type")
        if not client_type:
            raise ValueError("Client configuration must include a 'type' key.")

        client_type_lower = client_type.lower()
        client_class = cls._client_map.get(client_type_lower)

        if client_class:
            # Pass the full client_config to the client constructor
            return client_class(client_config=client_config, metrics_logger=metrics_logger)
        else:
            # Consider if we want to dynamically import here in the future
            # For now, rely on pre-registration or direct mapping
            raise ValueError(f"Unsupported LLM client type: {client_type}")

# Example of how actual clients might be registered if they are in separate files:
# from llm_pipeline.clients.gemini_client import GeminiAPIClient # Assuming this exists
# LLMClientFactory.register_client("gemini", GeminiAPIClient)
# This would typically be done in an __init__.py or a central registration point.
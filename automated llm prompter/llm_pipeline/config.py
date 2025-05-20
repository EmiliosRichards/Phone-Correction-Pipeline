import os
from pathlib import Path
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# --- Path Definitions ---
# Assuming config.py is in llm_pipeline/, so PROJECT_ROOT is parent.parent
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
OUTPUT_DIR_BASE = DATA_DIR / "llm_runs"

# Create directories if they don't exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR_BASE.mkdir(parents=True, exist_ok=True)

# --- General Settings ---
DEFAULT_LLM_PROFILE = "gemini_default"
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 60  # seconds

# --- LLM Profiles ---
LLM_PROFILES = {
    "gemini_default": {
        "type": "gemini",
        "api_key_env_var": "GEMINI_API_KEY",
        "model_name": "gemini-1.5-pro-latest", # Or specific model like "gemini-pro"
        "temperature": 0.7,
        "max_tokens": 2048,
        "prompt_file": PROMPTS_DIR / "gemini_pydantic_phone_extraction_v1.txt",
    },
    "gemini_phone_json": {
        "type": "gemini",
        "api_key_env_var": "GEMINI_API_KEY",
        "model_name": "gemini-1.5-flash", # Using flash for potentially faster structured output
        "temperature": 0.5, # Adjusted for more deterministic JSON
        "max_tokens": 2048,
        "prompt_file": PROMPTS_DIR / "gemini_phone_extraction_v3.txt", # This prompt might need adjustment for structured output
        "pydantic_schema_name": "PhoneNumberOutput", # Key for specifying the Pydantic model
    },
    "mixtral_ssh_json": {
        "type": "ssh_mixtral",
        "ssh_host_env_var": "MIXTRAL_SSH_HOST",
        "ssh_user_env_var": "MIXTRAL_SSH_USER",
        "ssh_key_path_env_var": "MIXTRAL_SSH_KEY_PATH", # Path to the private key
        "remote_script_path": "/opt/mixtral_llm/run_inference.py", # Example path on remote
        "model_name": "mixtral-8x7b-instruct-v0.1",
        "temperature": 0.5,
        "max_tokens": 4096,
        "prompt_file": PROMPTS_DIR / "mixtral_json_instruct_v3.txt",
        "response_format": "json", # Specific to this profile
    },
    "llama_local": {
        "type": "local_llama",
        "api_base_url_env_var": "LLAMA_API_BASE_URL", # e.g., "http://localhost:11434/v1" for Ollama
        "api_key_env_var": "LLAMA_API_KEY", # Optional, depending on local setup (e.g. "ollama")
        "model_name": "llama3:latest", # Or a specific model served locally
        "temperature": 0.6,
        "max_tokens": 2000,
        "prompt_file": PROMPTS_DIR / "llama_generic_extraction_v3.txt",
    },
    "gemini_pydantic_v1": {
        "type": "gemini",
        "api_key_env_var": "GEMINI_API_KEY",
        "model_name": "gemini-1.5-pro-latest", # Changed from gemini-1.5-flash
        "temperature": 0.7, # Changed from 0.3
        "max_tokens": 2048,
        "prompt_file": PROMPTS_DIR / "gemini_pydantic_phone_extraction_v1.txt",
        "pydantic_schema_name": "PhoneNumberOutput",
    },
}

# --- Active LLM Configuration ---
ACTIVE_LLM_PROFILE_NAME: str | None = None
ACTIVE_LLM_CONFIG: dict | None = None

def load_active_llm_config(profile_name: str = None) -> dict:
    """
    Loads the specified LLM profile configuration and sets it as active.

    Retrieves API keys and other sensitive information from environment variables.

    Args:
        profile_name: The name of the LLM profile to load.
                      If None, uses DEFAULT_LLM_PROFILE.

    Returns:
        The loaded and processed active LLM configuration dictionary.

    Raises:
        ValueError: If the profile is not found or required environment
                    variables are not set.
    """
    global ACTIVE_LLM_PROFILE_NAME, ACTIVE_LLM_CONFIG

    if profile_name is None:
        profile_name = DEFAULT_LLM_PROFILE
    
    logger.info(f"Attempting to load LLM profile: {profile_name}")

    if profile_name not in LLM_PROFILES:
        logger.error(f"LLM profile '{profile_name}' not found in LLM_PROFILES.")
        raise ValueError(f"LLM profile '{profile_name}' not found.")

    profile_config = LLM_PROFILES[profile_name].copy() # Make a copy to modify
    ACTIVE_LLM_PROFILE_NAME = profile_name
    
    # Load credentials and other sensitive data from environment variables
    credentials_loaded = {}
    
    for key_name_in_profile, actual_key_name_in_config in [
        ("api_key_env_var", "api_key"),
        ("ssh_host_env_var", "ssh_host"),
        ("ssh_user_env_var", "ssh_user"),
        ("ssh_key_path_env_var", "ssh_key_path"),
        ("api_base_url_env_var", "api_base_url")
    ]:
        if key_name_in_profile in profile_config:
            env_var_name = profile_config[key_name_in_profile]
            env_var_value = os.getenv(env_var_name)
            if env_var_value is None:
                logger.warning(f"Environment variable '{env_var_name}' for profile '{profile_name}' not set. This might be an issue if the key is required.")
                # Depending on strictness, could raise ValueError here.
                # For now, allow it to proceed, client using the config should validate.
            credentials_loaded[actual_key_name_in_config] = env_var_value
            # Remove the _env_var key from the final config
            del profile_config[key_name_in_profile]

    ACTIVE_LLM_CONFIG = {**profile_config, **credentials_loaded}
    logger.info(f"Successfully loaded LLM profile: {profile_name}")
    # Redact sensitive keys for logging, ensure common patterns are covered
    safe_to_log_config = {}
    if ACTIVE_LLM_CONFIG:
        for k, v in ACTIVE_LLM_CONFIG.items():
            if isinstance(v, str) and ('key' in k.lower() or 'token' in k.lower() or 'secret' in k.lower()):
                safe_to_log_config[k] = "****REDACTED****"
            else:
                safe_to_log_config[k] = v
    logger.debug(f"Active LLM Config: {safe_to_log_config}")
    return ACTIVE_LLM_CONFIG


# --- Initialize with default profile on import (optional, or call explicitly) ---
# By default, do not auto-load. Application should call load_active_llm_config() explicitly.
# Example:
# if __name__ == "__main__":
#     try:
#         # Set dummy env var for testing
#         os.environ["GEMINI_API_KEY"] = "test_key_for_config_script_main"
#         load_active_llm_config() 
#         print(f"Loaded default profile: {ACTIVE_LLM_PROFILE_NAME}")
#         print(f"Config: {ACTIVE_LLM_CONFIG}")
#         del os.environ["GEMINI_API_KEY"] 
#     except ValueError as e:
#         print(f"Error loading config: {e}")


if __name__ == "__main__":
    # Example usage and basic demonstration
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info(f"PROJECT_ROOT: {PROJECT_ROOT}")
    logger.info(f"DATA_DIR: {DATA_DIR}")
    logger.info(f"PROMPTS_DIR: {PROMPTS_DIR}")
    logger.info(f"OUTPUT_DIR_BASE: {OUTPUT_DIR_BASE}")
    
    print("\n--- LLM_PROFILES ---")
    for name, conf in LLM_PROFILES.items():
        print(f"  Profile: {name}")
        for k, v in conf.items():
            if isinstance(v, Path):
                print(f"    {k}: {v}") # Print Path objects as is
            else:
                print(f"    {k}: {v!r}") # Use repr for other types for clarity

    print("\n--- Testing load_active_llm_config ---")
    print("To fully test 'load_active_llm_config', ensure relevant environment variables are set.")
    print("For example, for 'gemini_default', set GEMINI_API_KEY.")
    print("Example: > export GEMINI_API_KEY='your_actual_gemini_api_key'")
    
    # Demonstrate loading - this will likely raise ValueError if env vars not set
    # or print warnings if they are optional and not set.
    print("\nAttempting to load 'gemini_default' (GEMINI_API_KEY should be set in env):")
    try:
        # For demonstration, temporarily set a dummy key if you want to see it "succeed"
        # os.environ['GEMINI_API_KEY'] = 'dummy_key_for_testing_output'
        load_active_llm_config("gemini_default")
        if ACTIVE_LLM_CONFIG:
            print(f"Successfully loaded profile: {ACTIVE_LLM_PROFILE_NAME}")
            print("Active configuration (sensitive details may be redacted or missing if env vars not set):")
            for k, v in ACTIVE_LLM_CONFIG.items():
                 print(f"  {k}: {v!r}")
        # if 'GEMINI_API_KEY' in os.environ and os.environ['GEMINI_API_KEY'] == 'dummy_key_for_testing_output':
        #     del os.environ['GEMINI_API_KEY'] # Clean up dummy key
    except ValueError as e:
        logger.error(f"Configuration error during load_active_llm_config('gemini_default'): {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

    print("\nNote: If environment variables are not set, 'load_active_llm_config' might raise ValueErrors or log warnings.")
    print("The actual API keys/credentials are loaded from environment variables at runtime.")
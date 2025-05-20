# LLM Phone Number Extraction Pipeline

**Overview:**
*   Briefly describe the project's purpose: to extract and classify phone numbers from text using various Large Language Models (LLMs).
*   Mention supported LLMs: Gemini, local Llama, SSH Mixtral.

**Features:**
*   Support for multiple LLMs (Gemini, local Llama, SSH Mixtral) via simple configuration.
*   Structured JSON output for easy parsing and integration.
*   Schema validation of LLM outputs against predefined categories to ensure data quality.
*   Configurable LLM profiles: Easily switch between different models, API keys, and specific model parameters through `llm_pipeline/config.py`.
*   Externalized prompt templates: Prompts are stored in the `prompts/` directory, allowing for easy modification and versioning without code changes.
*   Detailed logging: Comprehensive logs for pipeline execution and debugging.
*   Run metrics: Collection of metrics for API calls and overall run performance.

**Directory Structure:**
*   `llm_pipeline/`: Contains the core pipeline logic.
    *   `main.py`: The main executable script for running the pipeline.
    *   `config.py`: Central configuration file for LLM profiles, API keys, and other settings.
*   `llm_pipeline/clients/`: Houses the specific client implementations for interacting with different LLMs (e.g., `gemini_client.py`, `local_llama_client.py`, `ssh_mixtral_client.py`).
*   `llm_pipeline/common/`: Includes shared utilities and modules for:
    *   Schema validation (`schema_utils.py`)
    *   Logging (`log.py`)
    *   Metrics collection (`metrics.py`)
    *   Input/Output operations (`io_utils.py`)
*   `prompts/`: Stores all LLM prompt templates (e.g., `gemini_phone_extraction_v3.txt`, `mixtral_json_instruct_v3.txt`, `llama_generic_extraction_v3.txt`).
*   `data/llm_runs/`: Default base directory where all outputs from pipeline runs are stored. Each run creates a unique subdirectory here.

**Core Script:**
*   The primary entry point for the pipeline is [`llm_pipeline/main.py`](llm_pipeline/main.py:0).

**Setup:**
*   **Python Version:** Requires Python 3.8 or newer.
*   **Dependencies:**
    *   Install dependencies using a `requirements.txt` file (user is expected to manage this, e.g., `pip install -r requirements.txt`).
    *   Key dependencies include:
        *   `google-generativeai`: For using the Gemini LLM.
        *   `requests`: For HTTP requests (often used by local LLM clients).
        *   `paramiko`: For SSH connections (used by the SSH Mixtral client).
        *   `nltk`: For natural language text processing.
    *   **NLTK Data (Punkt Tokenizer):**
        *   This project uses `nltk` for advanced text processing, specifically sentence tokenization. After installing dependencies via `requirements.txt`, you may need to download the `punkt` tokenizer models.
        *   You can do this by running the following in a Python interpreter:
          ```python
          import nltk
          nltk.download('punkt')
          ```
*   **Environment Variables (Crucial for Operation):**
    *   These variables store sensitive credentials and must be set in your environment *before* running the pipeline.
    *   **For Gemini:**
        *   `GEMINI_API_KEY`: Your API key for Google Gemini services.
    *   **For SSH Mixtral:**
        *   `MIXTRAL_SSH_HOST`: Hostname or IP address of the SSH server.
        *   `MIXTRAL_SSH_USER`: Username for the SSH connection.
        *   `MIXTRAL_SSH_KEY_PATH`: Absolute path to your private SSH key file.
    *   **For Local Llama (e.g., Ollama):**
        *   `LLAMA_API_BASE_URL`: The base URL of your local Llama API endpoint (e.g., `http://localhost:11434/v1`).
        *   `LLAMA_API_KEY` (Optional): API key if your local Llama setup requires one (e.g., "ollama" for some Ollama setups).

**Basic Usage Example:**
*   To run the pipeline with the default Gemini profile on text files in a directory:
```bash
python llm_pipeline/main.py --input-dir path/to/your/text_files --llm-profile gemini_default
```

**Further Information:**
*   For detailed instructions on configuration, advanced usage, command-line arguments, and output structure, please refer to the [LLM Pipeline Usage Guide](llm_pipeline/USAGE.md).
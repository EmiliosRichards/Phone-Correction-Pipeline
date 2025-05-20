# LLM Pipeline Usage Guide

**Introduction:**
*   Reiterate the pipeline's purpose: extracting and classifying phone numbers from text documents using configurable LLMs.
*   Emphasize that this guide provides detailed information on configuring and running the pipeline.

**Prerequisites & Setup:**

*   **Python Version:** Requires Python 3.8 or newer.
*   **Dependencies:**
*   Install dependencies using the provided `requirements.txt` file:
  ```bash
  pip install -r requirements.txt
  ```
*   Key dependencies include `google-generativeai`, `requests`, `paramiko`, and `nltk`.
*   **NLTK Data (Punkt Tokenizer):**
*   This project uses `nltk` for advanced text processing, specifically sentence tokenization. After installing dependencies, you may need to download the `punkt` tokenizer models.
*   You can do this by running the following in a Python interpreter:
  ```python
  import nltk
  nltk.download('punkt')
  ```
*   **Environment Variables:** Ensure all necessary environment variables for your chosen LLM(s) are set (see specific profile sections below).

**Configuration (`llm_pipeline/config.py`):**
*   Explain that [`llm_pipeline/config.py`](llm_pipeline/config.py:0) is the central place for all pipeline configurations.
*   **`LLM_PROFILES` Structure:**
    *   This dictionary defines different configurations for various LLMs. Each key is a profile name (e.g., "gemini_default"), and the value is another dictionary containing parameters for that profile.
*   **Detailed Profile Explanations:**
    *   **`gemini_default`** (Profile for Google Gemini):
        *   **Purpose:** Designed for general-purpose phone number extraction using Google's Gemini models.
        *   **Key Parameters:**
            *   `type: "gemini"`: Identifies the client type.
            *   `api_key_env_var: "GEMINI_API_KEY"`: Specifies the environment variable holding the API key.
            *   `model_name: "gemini-1.5-pro-latest"`: The specific Gemini model to use.
            *   `prompt_file: PROMPTS_DIR / "gemini_phone_extraction_v3.txt"`: Path to the prompt file tailored for Gemini.
        *   **Required Environment Variable:** `GEMINI_API_KEY`.
    *   **`mixtral_ssh_json`** (Profile for Mixtral via SSH):
        *   **Purpose:** For running inference with a Mixtral model hosted on a remote server accessible via SSH, configured to return JSON.
        *   **Key Parameters:**
            *   `type: "ssh_mixtral"`
            *   `ssh_host_env_var: "MIXTRAL_SSH_HOST"`
            *   `ssh_user_env_var: "MIXTRAL_SSH_USER"`
            *   `ssh_key_path_env_var: "MIXTRAL_SSH_KEY_PATH"`
            *   `remote_script_path: "/opt/mixtral_llm/run_inference.py"` (Example): Path to the inference script on the remote server.
            *   `model_name: "mixtral-8x7b-instruct-v0.1"`
            *   `prompt_file: PROMPTS_DIR / "mixtral_json_instruct_v3.txt"`
            *   `response_format: "json"`: Instructs the client to expect JSON.
        *   **Required Environment Variables:** `MIXTRAL_SSH_HOST`, `MIXTRAL_SSH_USER`, `MIXTRAL_SSH_KEY_PATH`.
    *   **`llama_local`** (Profile for Local Llama):
        *   **Purpose:** For using Llama models served locally (e.g., via Ollama or a similar tool).
        *   **Key Parameters:**
            *   `type: "local_llama"`
            *   `api_base_url_env_var: "LLAMA_API_BASE_URL"`
            *   `api_key_env_var: "LLAMA_API_KEY"` (Optional, depends on local setup)
            *   `model_name: "llama3:latest"` (Example, use the model name as served by your local instance)
            *   `prompt_file: PROMPTS_DIR / "llama_generic_extraction_v3.txt"`
        *   **Required Environment Variables:** `LLAMA_API_BASE_URL`, and optionally `LLAMA_API_KEY`.
*   **`DEFAULT_LLM_PROFILE`:**
    *   Value: `"gemini_default"` (as per [`llm_pipeline/config.py`](llm_pipeline/config.py:21)).
    *   This is the profile used if you don't specify one with the `--llm-profile` command-line argument.
*   **`OUTPUT_DIR_BASE`:**
    *   Value: `PROJECT_ROOT / "data" / "llm_runs"` (as per [`llm_pipeline/config.py`](llm_pipeline/config.py:13)).
    *   This is the default base directory where output folders for each run will be created. You can override this with the `--output-dir` argument.
*   **How to Adjust Settings:**
    *   To change the default LLM, modify the `DEFAULT_LLM_PROFILE` string.
    *   To adjust parameters for an existing profile (e.g., temperature, max_tokens, model_name), edit the corresponding dictionary within `LLM_PROFILES`.
    *   To add a new LLM profile, add a new entry to the `LLM_PROFILES` dictionary, following the structure of existing profiles and ensuring you have a corresponding client implementation if it's a new `type`.

**Running the Pipeline (`llm_pipeline/main.py`):**
*   The pipeline is executed using `python llm_pipeline/main.py` from the project root directory.
*   **Command-Line Arguments (from [`llm_pipeline/main.py`](llm_pipeline/main.py:21-70)):**
    *   `--input-dir <path>` (Required): Specifies the path to the directory containing your input text files.
        *   Example: `--input-dir data/source_documents`
    *   `--input-pattern "<pattern>"` (Default: `*.txt`): A glob pattern to select specific files within the `--input-dir`.
        *   Example: `--input-pattern "*.pdf"` (if PDF processing is supported) or `--input-pattern "report_*.txt"`
    *   `--llm-profile <profile_name>` (Default: uses `DEFAULT_LLM_PROFILE` from `config.py`): The name of the LLM profile to use from `LLM_PROFILES` in `config.py`.
        *   Example: `--llm-profile mixtral_ssh_json`
    *   `--output-dir <path>` (Default: uses `OUTPUT_DIR_BASE` from `config.py`): Allows you to specify a custom base directory for saving run outputs. A run-specific subfolder will still be created within this path.
        *   Example: `--output-dir /mnt/processed_data/llm_extractions`
    *   `--run-description <description>` (Default: `llm_run`): A short, descriptive name for the current run. This will be part of the output directory's name.
        *   Example: `--run-description "sales_contacts_extraction_q2"`
    *   `--limit <number>` (Default: `None`, processes all files): Limits the pipeline to process only the specified number of input files. Useful for testing.
        *   Example: `--limit 5`
    *   `--save-raw-response` (Action Flag, disabled by default): If included, the raw, unprocessed response from the LLM will be saved in the `raw_responses/` output subdirectory.
        *   Example: `python llm_pipeline/main.py ... --save-raw-response`
    *   `--overwrite-outputs` (Action Flag, disabled by default): **Currently not implemented.** (As noted in [`llm_pipeline/main.py`](llm_pipeline/main.py:63)). If implemented, this would allow overwriting existing output files.
*   **Usage Examples:**
    *   **Using Gemini with a specific run description:**
        ```bash
        python llm_pipeline/main.py --input-dir ../data/sample_texts --llm-profile gemini_default --run-description gemini_initial_test
        ```
        *(Note: Adjust `../data/sample_texts` relative to where `main.py` is if you run it from `llm_pipeline/` directory itself. The examples assume running from project root.)*
    *   **Using Local Llama, processing only 10 files, and saving raw responses:**
        ```bash
        python llm_pipeline/main.py --input-dir ../data/large_dataset --llm-profile llama_local --limit 10 --save-raw-response
        ```
    *   **Using SSH Mixtral with a custom output directory:**
        ```bash
        python llm_pipeline/main.py --input-dir ../data/confidential_docs --llm-profile mixtral_ssh_json --output-dir /secure_storage/llm_outputs --run-description mixtral_secure_run
        ```

**Output Structure:**
*   Each pipeline run creates a unique subdirectory within the `OUTPUT_DIR_BASE` (default: `data/llm_runs/`) or your custom `--output-dir`.
*   The run-specific directory is named using the format: `<timestamp>_<run_description>_<llm_type>` (e.g., `20250515_093000_gemini_test_run_gemini`).
*   **Inside each run-specific directory, you'll find (based on `setup_run_environment` in [`llm_pipeline/main.py`](llm_pipeline/main.py:85-88)):**
    *   `results/`: Contains the processed JSON output files, one for each successfully processed input file (e.g., `inputfile1.json`, `inputfile2.json`).
    *   `raw_responses/`: If `--save-raw-response` was used, this directory contains the raw text responses from the LLM, one for each processed input file (e.g., `inputfile1_raw.txt`).
    *   `logs/`: Contains log files for the run:
        *   `pipeline.log`: General operational logs.
        *   `debug.log`: More detailed debug information.
    *   `metrics/`: Contains files with metrics about the run:
        *   `api_calls.jsonl`: A JSON Lines file logging details of each API call made to the LLM.
        *   `run_summary.json`: A JSON file summarizing the entire run (e.g., total files processed, success/failure counts, duration).
    *   `config_snapshot.json`: A JSON file containing a snapshot of the LLM profile configuration used for that specific run (sensitive details like API keys are redacted).

**Prompts (`prompts/` directory):**
*   All prompt templates used by the LLMs are externalized in the [`prompts/`](prompts/:0) directory. This allows for easy editing and experimentation with prompts without changing the pipeline code.
*   **Current v3 Prompts:**
    *   [`prompts/gemini_phone_extraction_v3.txt`](prompts/gemini_phone_extraction_v3.txt:0): Tailored for phone number extraction tasks using Gemini models.
    *   [`prompts/mixtral_json_instruct_v3.txt`](prompts/mixtral_json_instruct_v3.txt:0): Designed for Mixtral models, especially when using instruction-following capabilities and expecting JSON output.
    *   [`prompts/llama_generic_extraction_v3.txt`](prompts/llama_generic_extraction_v3.txt:0): A more generic extraction prompt suitable for various Llama-based models.
*   **How Prompts are Linked:** The `prompt_file` key within each profile in `LLM_PROFILES` (in [`llm_pipeline/config.py`](llm_pipeline/config.py:0)) specifies which prompt file from the `prompts/` directory that profile will use.

**Schema (`llm_pipeline/common/schema_utils.py`):**
*   The pipeline validates the LLM's output to ensure it conforms to a predefined schema, promoting data consistency.
*   The core of the schema involves identifying phone numbers and classifying them.
*   **`PhoneCategory` Enum:** The `category` field in the output JSON for each phone number must be one of the following valid values (defined in [`llm_pipeline/common/schema_utils.py`](llm_pipeline/common/schema_utils.py:10-16)):
    *   `"Sales"`
    *   `"Support"`
    *   `"Recruiting"`
    *   `"General"`
    *   `"LowValue"`

**Troubleshooting (Common Issues & Tips):**
*   **API Key Errors:**
    *   If you see errors related to authentication or API keys (e.g., "API key not valid," "Permission denied").
    *   **Solution:** Double-check that the correct environment variable (e.g., `GEMINI_API_KEY`) is set in your terminal session or system environment *before* running the script. Ensure the key itself is correct and has the necessary permissions.
*   **SSH Connection Problems (for `mixtral_ssh_json` profile):**
    *   Errors like "Connection refused," "Authentication failed," or "Key file not found."
    *   **Solutions:**
        *   Verify `MIXTRAL_SSH_HOST`, `MIXTRAL_SSH_USER` are correct.
        *   Ensure `MIXTRAL_SSH_KEY_PATH` points to the correct *absolute* path of your private SSH key.
        *   Check that your SSH key is added to your SSH agent or has correct file permissions (e.g., `chmod 600 ~/.ssh/your_private_key`).
        *   Confirm the remote server is reachable and the SSH service is running.
*   **Model Not Found Errors:**
    *   The LLM client reports it cannot find or access the specified model (e.g., "Model 'llama3-nonexistent' not found").
    *   **Solution:** Check the `model_name` parameter in the active LLM profile in [`llm_pipeline/config.py`](llm_pipeline/config.py:0). Ensure it matches a model available to your API key (for cloud LLMs) or served by your local instance (for local LLMs).
*   **File Not Found (Input Files or Prompt Files):**
    *   Errors like "No such file or directory" for input files or prompt templates.
    *   **Solutions:**
        *   For `--input-dir`, ensure the path is correct and accessible.
        *   For prompt files, ensure the path specified in the `LLM_PROFILES` (in `config.py`) correctly points to an existing file within the `prompts/` directory.
*   **Configuration Issues:**
    *   If the pipeline behaves unexpectedly, review your active LLM profile in `config.py` and the command-line arguments you used.
    *   Check the `logs/pipeline.log` and `logs/debug.log` in the run output directory for more detailed error messages.
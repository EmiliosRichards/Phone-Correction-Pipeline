# Phone Validation Pipeline - Usage Guide

This document provides detailed instructions for setting up, configuring, and running the Phone Validation Pipeline.

## Table of Contents

- [Phone Validation Pipeline - Usage Guide](#phone-validation-pipeline---usage-guide)
  - [Table of Contents](#table-of-contents)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Detailed Setup](#2-detailed-setup)
    - [Python Version](#python-version)
    - [Virtual Environment](#virtual-environment)
    - [Install Dependencies](#install-dependencies)
    - [Playwright Browser Installation](#playwright-browser-installation)
    - [Environment Variables (`.env` file)](#environment-variables-env-file)
  - [3. Input Data Format](#3-input-data-format)
  - [4. Running the Pipeline (`main_pipeline.py`)](#4-running-the-pipeline-main_pipelinepy)
    - [Command](#command)
    - [Operation](#operation)
    - [Outputs](#outputs)
    - [Output Directory Structure](#output-directory-structure)
  - [5. Running the Reporting Script (`generate_report.py`)](#5-running-the-reporting-script-generate_reportpy)
    - [Command](#command-1)
    - [Arguments](#arguments)
    - [Outputs](#outputs-1)
  - [6. Configuration](#6-configuration)
    - [Via `.env` File](#via-env-file)
    - [Via `src/core/config.py`](#via-srccoreconfigpy)
  - [7. Troubleshooting](#7-troubleshooting)

## 1. Prerequisites

*   **Python**: Version 3.8 or higher is recommended.
*   **Access to Google Gemini API**: A valid API key is required for the LLM extraction component.
*   **Internet Connection**: For web scraping and accessing the Gemini API.

## 2. Detailed Setup

### Python Version

Ensure you have Python 3.8+ installed. You can check your Python version by running:
```bash
python --version
```

### Virtual Environment

It is strongly recommended to use a Python virtual environment to manage project dependencies and avoid conflicts with other Python projects.

*   **Create a virtual environment** (if you haven't already):
    ```bash
    python -m venv venv
    ```
    This creates a `venv` directory in your project folder.

*   **Activate the virtual environment**:
    *   On Windows (Git Bash or CMD):
        ```bash
        .\venv\Scripts\activate
        ```
    *   On macOS/Linux:
        ```bash
        source venv/bin/activate
        ```
    Your command prompt should now indicate that you are in the `(venv)` environment.

### Install Dependencies

All required Python packages are listed in the [`requirements.txt`](./requirements.txt:1) file. Install them using pip:
```bash
pip install -r requirements.txt
```
This will install libraries such as Pandas, Playwright, `python-phonenumbers`, Google Generative AI SDK, etc.

### Playwright Browser Installation

Playwright uses browser binaries for web automation. You need to install these browsers:
```bash
playwright install
```
This command downloads and sets up the necessary browser drivers (Chromium, Firefox, WebKit) that Playwright will use. If you only want a specific browser, you can specify it, e.g., `playwright install chromium`.

### Environment Variables (`.env` file)

The application uses a `.env` file to manage configurations, API keys, and file paths. This keeps sensitive information out of the codebase and allows for easy customization.

1.  **Create the `.env` file**:
    Copy the example file [`.env.example`](./.env.example:1) to a new file named `.env` in the `phone_validation_pipeline` root directory:
    ```bash
    # On Windows
    copy .env.example .env

    # On macOS/Linux
    cp .env.example .env
    ```

2.  **Edit the `.env` file**:
    Open the `.env` file with a text editor and fill in the values. Below are explanations for each variable defined in [`.env.example`](./.env.example:1) and used by [`src/core/config.py`](./src/core/config.py:1):

    *   **`GEMINI_API_KEY`** (Required)
        *   Description: Your API key for the Google Gemini service. This is essential for the LLM extraction component.
        *   Example: `GEMINI_API_KEY="AIzaSyYOURACTUALAPIKEYHERE"`

    *   **`INPUT_EXCEL_FILE_PATH`** (Required)
        *   Description: The path to your input data file (Excel or CSV). This path should be relative to the `phone_validation_pipeline` directory.
        *   Example: `INPUT_EXCEL_FILE_PATH="data_to_be_inputed.xlsx"` or `INPUT_EXCEL_FILE_PATH="../data_sources/my_companies.csv"`

    *   **`SCRAPER_USER_AGENT`**
        *   Description: The User-Agent string the scraper will use for HTTP requests.
        *   Default: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36`

    *   **`SCRAPER_PAGE_TIMEOUT_MS`**
        *   Description: Default timeout for Playwright page operations in milliseconds (e.g., waiting for a page to load).
        *   Default: `30000` (30 seconds)

    *   **`SCRAPER_NAVIGATION_TIMEOUT_MS`**
        *   Description: Default timeout for Playwright navigation actions in milliseconds.
        *   Default: `60000` (60 seconds)

    *   **`SCRAPER_MAX_RETRIES`**
        *   Description: Maximum number of retries for a failed scraping attempt on a URL.
        *   Default: `2`

    *   **`SCRAPER_RETRY_DELAY_SECONDS`**
        *   Description: Delay in seconds between scraping retries.
        *   Default: `5`

    *   **`TARGET_LINK_KEYWORDS`**
        *   Description: Comma-separated list of keywords used to identify relevant internal links to scrape (e.g., "contact", "about us"). Case-insensitive.
        *   Default: `contact,about,support,impressum,kontakt,legal,privacy,terms`

    *   **`MAX_DEPTH_INTERNAL_LINKS`**
        *   Description: Maximum depth to follow internal links from the initial company URL. A depth of `0` means only the initial URL is scraped. A depth of `1` means the initial URL and any direct links from it (matching keywords) are scraped.
        *   Default: `1`

    *   **`RESPECT_ROBOTS_TXT`**
        *   Description: Whether the scraper should respect the `robots.txt` file of websites. Set to `True` or `False`.
        *   Default: `True`

    *   **`ROBOTS_TXT_USER_AGENT`**
        *   Description: The user-agent string to use when checking `robots.txt`. `*` means it applies to all user-agents.
        *   Default: `*`

    *   **`OUTPUT_BASE_DIR`**
        *   Description: The base directory where all output files (processed data, scraped content, LLM context) will be saved. This path is relative to the `phone_validation_pipeline` directory. The directory will be created if it doesn't exist.
        *   Default: `output_data`

    *   **`LLM_MODEL_NAME`**
        *   Description: The specific Google Gemini model to use for extraction.
        *   Default: `gemini-1.5-pro-latest`
        *   Other options: `gemini-1.5-flash-latest`, etc. (ensure your API key has access).

    *   **`LLM_TEMPERATURE`**
        *   Description: Controls the randomness of the LLM's output. Higher values (e.g., 0.8) make output more random, while lower values (e.g., 0.2) make it more deterministic.
        *   Default: `0.5`

    *   **`LLM_MAX_TOKENS`**
        *   Description: Maximum number of tokens the LLM can generate in its response.
        *   Default: `2048`

    *   **`LLM_PROMPT_TEMPLATE_PATH`**
        *   Description: Path to the text file containing the prompt template for the LLM. Relative to the `phone_validation_pipeline` directory.
        *   Default: `prompts/gemini_phone_validation_v1.txt`

    *   **`TARGET_COUNTRY_CODES`**
        *   Description: Comma-separated list of ISO 3166-1 alpha-2 country codes (e.g., US, GB, DE) to help the `python-phonenumbers` library parse numbers more accurately. Numbers will be validated against these regions.
        *   Default: `DE,CH,AT` (Germany, Switzerland, Austria)

    *   **`DEFAULT_REGION_CODE`**
        *   Description: A default ISO 3166-1 alpha-2 country code to use if a phone number cannot be parsed with a specific country context. This helps in formatting numbers that don't have an international prefix.
        *   Default: `DE`

    *   **`OUTPUT_EXCEL_FILE_NAME_TEMPLATE`**
        *   Description: Template for the main output Excel file name. `{run_id}` will be replaced with the actual run ID (timestamp).
        *   Default: `phone_validation_output_{run_id}.xlsx`

## 3. Input Data Format

The pipeline expects an input file (Excel `.xlsx` or CSV `.csv`) specified by `INPUT_EXCEL_FILE_PATH` in the `.env` file. This file must contain the following columns:

*   **`CompanyName`** (Required): The name of the company.
    *   Type: Text
*   **`GivenURL`** (Required): The primary website URL for the company. The pipeline will start scraping from this URL.
    *   Type: Text (should be a valid URL, e.g., `http://example.com` or `https://www.example.com`)
*   **`GivenPhoneNumber`** (Optional but Recommended): The existing phone number for the company, if available. This can be in various formats.
    *   Type: Text

**Example `data_to_be_inputed.csv`:**
```csv
CompanyName,GivenURL,GivenPhoneNumber
Example Corp,https://www.example.com,+1-555-123-4567
Test Inc.,http://test-site.org,089/123456
Another Biz,www.anotherbiz.de,
```

If using an Excel file, these should be the headers in the first row of the first sheet.

## 4. Running the Pipeline (`main_pipeline.py`)

The [`main_pipeline.py`](./main_pipeline.py:1) script is the entry point to execute the entire phone validation process.

### Command
Navigate to the `phone_validation_pipeline` directory in your terminal (ensure your virtual environment is activated) and run:
```bash
python main_pipeline.py
```

### Operation
When executed, `main_pipeline.py` performs the following steps:
1.  **Initialization**: Loads configuration from `.env` and `src/core/config.py`. Sets up logging. Generates a unique `RunID` (timestamp based) for the current execution.
2.  **Data Loading**: Reads the input data from the file specified by `INPUT_EXCEL_FILE_PATH` using the `DataHandler`.
3.  **Processing Loop**: Iterates through each row (company) in the input data:
    *   **Scraping**: Uses the `ScraperLogic` to visit the `GivenURL` and relevant internal pages. Scraped text content is saved.
    *   **Regex Extraction**: The `RegexExtractorComponent` processes the scraped text to find phone numbers using predefined patterns.
    *   **LLM Extraction**: If regex fails or for further validation, the `LLMExtractorComponent` sends the scraped text (and other context) to the Google Gemini API to identify or confirm phone numbers.
    *   **Verification & Normalization**: Results from regex and LLM are compared. Found phone numbers are parsed, validated, and formatted using `python-phonenumbers` and the configured country codes.
    *   **Data Aggregation**: All extracted information (scraped text paths, found numbers, confidence scores, errors, etc.) is collected.
4.  **Output Generation**:
    *   The `DataHandler` saves the processed data, including new phone numbers and validation status, to an Excel file (e.g., `processed_data_with_phones.xlsx`) in the run-specific output directory.
    *   Raw scraped content and LLM interaction logs (context files) are also saved in subdirectories.

### Outputs
The main pipeline generates several outputs, organized within a run-specific directory:

*   **Main Processed Data File**: An Excel file (e.g., `output_data/[RunID]/phone_validation_output_[RunID].xlsx` or `processed_data_with_phones.xlsx` depending on older configurations) containing the original input data augmented with:
    *   Scraped URLs
    *   Status of scraping for each URL
    *   Phone numbers found by Regex
    *   Phone numbers found by LLM
    *   The final selected/validated phone number
    *   Confidence scores or notes about the findings
    *   Error messages if any step failed
*   **Scraped Content Files**: Raw HTML or text content saved from each successfully scraped webpage. These are typically stored in `output_data/[RunID]/scraped_content/`.
*   **LLM Context Files**: Files containing the prompts sent to the LLM and the raw responses received. These are useful for debugging and understanding LLM behavior, typically stored in `output_data/[RunID]/llm_context/`.

### Output Directory Structure
The default output directory structure looks like this:
```
output_data/
└── [RunID]/  (e.g., 20240516_113000)
    ├── scraped_content/
    │   ├── example.com_contact.html
    │   └── ... (other scraped files)
    ├── llm_context/
    │   ├── example.com_llm_prompt.txt
    │   ├── example.com_llm_response.json
    │   └── ... (other LLM files)
    ├── phone_validation_output_20240516_113000.xlsx (or processed_data_with_phones.xlsx)
    └── pipeline.log (if logging to file is configured for the run)
```
The `[RunID]` is typically a timestamp like `YYYYMMDD_HHMMSS` to ensure each run's outputs are kept separate.

## 5. Running the Reporting Script (`generate_report.py`)

The [`generate_report.py`](./generate_report.py:1) script is used to generate a summary report from the main pipeline's output Excel file. It also creates a queue of entries that might require manual review.

### Command
```bash
python generate_report.py <path_to_processed_excel_file> [--output_dir <directory>] [--run_id <identifier>]
```

### Arguments

*   **`<path_to_processed_excel_file>`** (Required):
    *   The full path to the main Excel output file generated by `main_pipeline.py`.
    *   Example: `output_data/20240516_113000/processed_data_with_phones.xlsx`

*   **`--output_dir <directory>`** (Optional):
    *   Specifies the directory where the report files (like `manual_review_queue.xlsx`) should be saved.
    *   If not provided, defaults to a `reports` subdirectory within the directory of the input Excel file, or the current directory if that fails.
    *   Example: `--output_dir custom_reports/`

*   **`--run_id <identifier>`** (Optional):
    *   A string identifier to include in the report output or filenames. If not provided, it might be inferred from the input file path or omitted.
    *   Example: `--run_id "Run_May16_Morning"`

### Outputs

*   **Console Summary**: The script prints a summary to the console, including:
    *   Total records processed.
    *   Number of phone numbers found/validated.
    *   Number of entries flagged for manual review.
*   **`manual_review_queue.xlsx`**: An Excel file created in the specified (or default) output directory. This file contains a subset of the processed data, specifically those entries where:
    *   No phone number could be found.
    *   Multiple conflicting phone numbers were found.
    *   The confidence in the found number is low.
    *   Errors occurred during processing.

## 6. Configuration

The pipeline's behavior can be customized in two main ways:

### Via `.env` File
This is the primary method for configuration. As detailed in the [Environment Variables](#environment-variables-env-file) section, you can adjust scraper settings, LLM parameters, file paths, and more by editing the `.env` file in the `phone_validation_pipeline` root. Changes to `.env` are loaded when the scripts start.

### Via `src/core/config.py`
The [`src/core/config.py`](./src/core/config.py:1) file defines the `AppConfig` class, which loads values from environment variables and provides default fallbacks.
*   **Modifying Defaults**: You can change the default values directly in `config.py` if an environment variable is not set. However, this is generally discouraged for instance-specific settings; `.env` is preferred.
*   **Adding New Configurations**: If new configurable parameters are needed for the application, they should be:
    1.  Added as attributes to the `AppConfig` class in `config.py`.
    2.  Loaded from `os.getenv()` within the `AppConfig.__init__` method, with a sensible default.
    3.  Documented with a corresponding entry in `.env.example`.

## 7. Troubleshooting

Here are some common issues and potential solutions:

*   **`GEMINI_API_KEY` not found or invalid**:
    *   **Symptom**: Errors related to "API key not valid" or "Authentication failed" when the LLM component runs.
    *   **Solution**:
        1.  Ensure your `GEMINI_API_KEY` in the `.env` file is correct and active.
        2.  Verify that the `.env` file is in the `phone_validation_pipeline` root directory and is being loaded (check for warning messages when scripts start).
        3.  Check your Google AI Studio or Cloud Console to ensure the API key is enabled and has the necessary permissions for the Gemini models.

*   **Playwright browser issues (e.g., "browser not found")**:
    *   **Symptom**: Errors during the scraping phase indicating Playwright cannot find or launch a browser.
    *   **Solution**:
        1.  Run `playwright install` again from your activated virtual environment to ensure browsers are correctly installed for the current Python environment.
        2.  Check for any conflicting Playwright installations or system PATH issues.

*   **Input file not found (`FileNotFoundError`)**:
    *   **Symptom**: `main_pipeline.py` exits early with a `FileNotFoundError`.
    *   **Solution**:
        1.  Verify that the `INPUT_EXCEL_FILE_PATH` in your `.env` file is correct.
        2.  Ensure the path is relative to the `phone_validation_pipeline` directory (e.g., `data/my_input.xlsx` if the file is in `phone_validation_pipeline/data/`).
        3.  Check for typos in the filename or path.

*   **Scraping issues (sites blocking, CAPTCHAs, dynamic content)**:
    *   **Symptom**: Scraper fails to retrieve content, gets empty pages, or encounters errors like timeouts or access denied.
    *   **Solution**:
        1.  Adjust `SCRAPER_PAGE_TIMEOUT_MS` and `SCRAPER_NAVIGATION_TIMEOUT_MS` in `.env` if sites are slow to load.
        2.  The current scraper has basic retry logic. For persistent blocks, more advanced techniques (proxy rotation, CAPTCHA solving services, more human-like interaction simulation) might be needed, which are beyond the current scope.
        3.  Ensure `RESPECT_ROBOTS_TXT` is set appropriately. Some sites may block if `robots.txt` is ignored.

*   **Incorrect phone number parsing/validation**:
    *   **Symptom**: Valid phone numbers are missed, or invalid ones are accepted.
    *   **Solution**:
        1.  Check `TARGET_COUNTRY_CODES` and `DEFAULT_REGION_CODE` in `.env`. Ensure they are relevant to the geographical scope of your input data.
        2.  The regex patterns in `regex_extractor_component.py` might need refinement for specific or unusual phone number formats.
        3.  The LLM prompt in `prompts/gemini_phone_validation_v1.txt` can be adjusted to improve its accuracy for phone number identification and formatting instructions.

*   **Dependencies not installed / ModuleNotFoundError**:
    *   **Symptom**: Python raises `ModuleNotFoundError` for a package like `pandas`, `playwright`, etc.
    *   **Solution**:
        1.  Ensure your virtual environment is activated.
        2.  Run `pip install -r requirements.txt` again to install any missing packages.

For issues not covered here, check the application logs (usually printed to the console, or in `pipeline.log` if configured) for more detailed error messages.
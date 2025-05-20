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
  - [5. Configuration Details](#5-configuration-details)
    - [Primary Configuration: `.env` File](#primary-configuration-env-file)
    - [Core Configuration Class: `src/core/config.py`](#core-configuration-class-srccoreconfigpy)
    - [Key Configuration Variables Explained](#key-configuration-variables-explained)
      - [General Project Settings](#general-project-settings)
      - [Web Scraper Settings](#web-scraper-settings)
      - [Advanced Link Prioritization \& Control](#advanced-link-prioritization--control)
      - [LLM (Gemini) Settings](#llm-gemini-settings)
      - [Phone Number Normalization](#phone-number-normalization)
      - [Logging Settings](#logging-settings)
  - [6. Troubleshooting](#6-troubleshooting)

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

All required Python packages are listed in the [`requirements.txt`](./requirements.txt) file. Install them using pip:
```bash
pip install -r requirements.txt
```
This will install libraries such as Pandas, Playwright, `python-phonenumbers`, Google Generative AI SDK, etc.

### Playwright Browser Installation

Playwright uses browser binaries for web automation. You need to install these browsers:
```bash
playwright install
```
This command downloads and sets up the necessary browser drivers (Chromium, Firefox, WebKit) that Playwright will use.

### Environment Variables (`.env` file)

The application uses a `.env` file to manage configurations, API keys, and file paths. This keeps sensitive information out of the codebase and allows for easy customization.

1.  **Create the `.env` file**:
    Copy the example file [`.env.example`](./.env.example) to a new file named `.env` in the project root directory:
    ```bash
    # On Windows
    copy .env.example .env

    # On macOS/Linux
    cp .env.example .env
    ```

2.  **Edit the `.env` file**:
    Open the `.env` file with a text editor and fill in the values. Detailed explanations for each variable are provided in the [Key Configuration Variables Explained](#key-configuration-variables-explained) section below. At a minimum, you will need to set:
    *   `GEMINI_API_KEY`
    *   `INPUT_EXCEL_FILE_PATH`

## 3. Input Data Format

The pipeline expects an input file (Excel `.xlsx` or CSV `.csv`) specified by `INPUT_EXCEL_FILE_PATH` in the `.env` file. This file must contain the following columns:

*   **`CompanyName`** (Required): The name of the company.
    *   Type: Text
*   **`GivenURL`** (Required): The primary website URL for the company. The pipeline will start scraping from this URL.
    *   Type: Text (should be a valid URL, e.g., `http://example.com` or `https://www.example.com`)
*   **`GivenPhoneNumber`** (Optional but Recommended): The existing phone number for the company, if available. This can be in various formats.
    *   Type: Text

**Example `data/data_to_be_inputed.csv`:**
```csv
CompanyName,GivenURL,GivenPhoneNumber
Example Corp,https://www.example.com,+1-555-123-4567
Test Inc.,http://test-site.org,089/123456
Another Biz,www.anotherbiz.de,
```
If using an Excel file, these should be the headers in the first row of the first sheet.

## 4. Running the Pipeline (`main_pipeline.py`)

The [`main_pipeline.py`](./main_pipeline.py) script is the entry point to execute the entire phone validation process.

### Command
Navigate to the project root directory in your terminal (ensure your virtual environment is activated) and run:
```bash
python main_pipeline.py
```

### Operation
When executed, `main_pipeline.py` performs the following steps:
1.  **Initialization**: Loads configuration from `.env` (via `src/core/config.py`). Sets up logging (file and console). Generates a unique `RunID` (timestamp-based) for the current execution.
2.  **Data Loading**: Reads the input data from the file specified by `INPUT_EXCEL_FILE_PATH`.
3.  **Processing Loop (Pass 1 - Scraping, LLM Processing, Caching)**: Iterates through each input row:
    *   Determines the `GivenURL`.
    *   Calls the `scrape_website` function, which uses advanced link prioritization and scoring to navigate the site and gather content. It returns scraped page details, a scraper status, and the final canonical entry URL for the site.
    *   If the canonical URL hasn't been processed yet in this run (checked against a cache):
        *   The `RegexExtractorComponent` processes scraped text for phone number patterns.
        *   The `LLMExtractorComponent` sends relevant text snippets and context to the Google Gemini API (which returns text that the application parses as JSON) to identify, confirm, and classify phone numbers.
        *   Raw LLM outputs for this pathful canonical URL are cached.
    *   The mapping from the original `GivenURL` to its true base domain (scheme + netloc) is stored.
4.  **Global Data Consolidation**: After processing all input rows, raw LLM outputs are aggregated by their true base domain. `process_and_consolidate_contact_data` is then called once per true base domain to de-duplicate phone numbers and aggregate their sources.
5.  **Output Generation (Pass 2 - Report Building)**: Uses the globally consolidated data:
    *   **Detailed Flattened Report** (`All_LLM_Extractions_Report_...`): Lists all unique phone numbers found by the LLM, associated with the original input `CompanyName`, but using data consolidated at the true base domain level. Includes aggregated types and source URLs for each number.
    *   **Summary Report** (`phone_validation_output_...`): Remains one row per original input entry. Populates top phone numbers and statuses by looking up the globally consolidated data for the input row's true base domain.
    *   **Top Contacts Report** (`Top_Contacts_Report_...`): Generates one consolidated row per unique true base domain. Features an aggregated company name (e.g., `[TrueBaseDomain] - OriginalCompA - OriginalCompB`), aggregated original GivenURLs, and a prioritized list of up to 3 phone numbers. Each phone number shows its aggregated types and a list of all original input companies that sourced that specific number for the true base domain.
    *   All reports, along with detailed logs and intermediate data dumps, are saved to a run-specific output directory.

### Outputs
The main pipeline generates several outputs, organized within a run-specific directory:

*   **Summary Report**: An Excel file (e.g., `output_data/[RunID]/phone_validation_output_[RunID].xlsx`) as described above. The exact filename is configured by `OUTPUT_EXCEL_FILE_NAME_TEMPLATE`.
*   **Detailed Flattened Report**: An Excel file (e.g., `output_data/[RunID]/All_LLM_Extractions_Report_[RunID].xlsx`).
*   **Top Contacts Report**: An Excel file (e.g., `output_data/[RunID]/Top_Contacts_Report_[RunID].xlsx`). The exact filename is configured by `TERTIARY_REPORT_FILE_NAME_TEMPLATE`.
*   **Run Log File**: A comprehensive log of the pipeline's execution (e.g., `output_data/[RunID]/pipeline_run_[RunID].log`).
*   **Scraped Content Files**: Cleaned text content from each successfully scraped webpage, stored in `output_data/[RunID]/scraped_content/cleaned_pages_text/`.
*   **Regex Snippets File**: JSON file containing aggregated regex-extracted snippets for each company, in `output_data/[RunID]/intermediate_data/`.
*   **LLM Prompt Input File**: The full prompt sent to the LLM for each company, in `output_data/[RunID]/llm_context/`.
*   **LLM Raw Output File**: The raw response received from the LLM, in `output_data/[RunID]/llm_context/`.

### Output Directory Structure
The default output directory structure looks like this:
```
output_data/
└── [RunID]/  (e.g., 20240520_113000)
    ├── pipeline_run_20240520_113000.log
    ├── scraped_content/
    │   └── cleaned_pages_text/
    │       └── CompanyName__domain_hash_cleaned.txt
    │       └── ... (other cleaned text files)
    ├── intermediate_data/
    │   └── CompanyName_RowX_regex_snippets.json
    │   └── ...
    ├── llm_context/
    │   ├── CompanyName_RowX_llm_prompt_input.txt
    │   ├── CompanyName_RowX_llm_raw_output.json (or similar, based on actual implementation)
    │   └── ...
    ├── phone_validation_output_20240520_113000.xlsx       # Summary Report
    ├── All_LLM_Extractions_Report_20240520_113000.xlsx    # Detailed Report
    └── Top_Contacts_Report_20240520_113000.xlsx           # Top Contacts Report
```
The `[RunID]` is a timestamp like `YYYYMMDD_HHMMSS`.

## 5. Configuration Details

### Primary Configuration: `.env` File
The primary method for configuring the pipeline is by creating and editing a `.env` file in the project's root directory. This file allows you to set various parameters without modifying the source code. Copy [`.env.example`](./.env.example) to `.env` and customize the values.

### Core Configuration Class: `src/core/config.py`
The [`src/core/config.py`](./src/core/config.py) file defines the `AppConfig` class. This class is responsible for:
1.  Loading configuration values from environment variables (defined in the `.env` file).
2.  Providing default values for settings if they are not specified in the `.env` file.
All configurable aspects of the pipeline are managed through this class.

### Key Configuration Variables Explained

Below is a detailed explanation of important variables you can set in your `.env` file. Refer to [`.env.example`](./.env.example) for a complete list and default examples.

#### General Project Settings
*   **`INPUT_EXCEL_FILE_PATH`** (Required)
    *   Description: Path to your input data file (Excel or CSV), relative to the project root.
    *   Example: `INPUT_EXCEL_FILE_PATH="data/my_companies.csv"`
*   **`ROW_PROCESSING_RANGE`**
    *   Description: Specifies a range or number of rows to process from the input. Examples: "10-20" (rows 10-20), "20" (first 20), "10-" (row 10 to end), "" (all rows).
    *   Default: `""` (process all)
*   **`OUTPUT_BASE_DIR`**
    *   Description: Base directory for all output files, relative to the project root.
    *   Default: `output_data`
*   **`OUTPUT_EXCEL_FILE_NAME_TEMPLATE`**
    *   Description: Template for the summary output Excel file. `{run_id}` is replaced by a timestamp.
    *   Default: `Pipeline_Summary_Report_{run_id}.xlsx` (Note: Default in `config.py` might differ, check `.env.example`)
*   **`TERTIARY_REPORT_FILE_NAME_TEMPLATE`**
    *   Description: Template for the "Top Contacts Report" Excel file. `{run_id}` is replaced.
    *   Default: `Top_Contacts_Report_{run_id}.xlsx`
    *   Note: The detailed report filename is `All_LLM_Extractions_Report_{run_id}.xlsx` (currently hardcoded pattern in `main_pipeline.py` but could be made configurable).
*   **`FILENAME_COMPANY_NAME_MAX_LEN`**
    *   Description: Maximum length for the sanitized company name part in generated filenames (e.g., for scraped content). Helps prevent path length errors.
    *   Default: `25`
    *   Guidance: Adjust based on your system's path length limits and your project's root path length. See [`.env.example`](./.env.example) for calculation guidance.

#### Web Scraper Settings
*   **`SCRAPER_USER_AGENT`**: User-Agent string for scraping.
    *   Default: A common browser User-Agent.
*   **`SCRAPER_PAGE_TIMEOUT_MS`**: Timeout for page operations (ms).
    *   Default: `30000` (30s)
*   **`SCRAPER_NAVIGATION_TIMEOUT_MS`**: Timeout for navigation actions (ms).
    *   Default: `60000` (60s)
*   **`SCRAPER_MAX_RETRIES`**: Max retries for a failed scrape attempt.
    *   Default: `2`
*   **`SCRAPER_RETRY_DELAY_SECONDS`**: Delay between scrape retries (s).
    *   Default: `5`
*   **`SCRAPER_NETWORKIDLE_TIMEOUT_MS`**: Timeout for Playwright's networkidle wait (ms). `0` to disable.
    *   Default: `3000` (3s)
*   **`MAX_DEPTH_INTERNAL_LINKS`**: Maximum depth to follow internal links. `0` = initial URL only, `1` = initial URL + direct relevant links.
    *   Default: `1`
*   **`RESPECT_ROBOTS_TXT`**: Whether to respect `robots.txt` (`True`/`False`).
    *   Default: `True`
*   **`ROBOTS_TXT_USER_AGENT`**: User-agent for `robots.txt` checks.
    *   Default: `*`

#### Advanced Link Prioritization & Control
These settings fine-tune how the scraper discovers and prioritizes links:
*   **`TARGET_LINK_KEYWORDS`**:
    *   Description: Comma-separated general keywords. A link's text or URL must contain one of these to be considered for scoring. Acts as an initial gate.
    *   Example: `TARGET_LINK_KEYWORDS=contact,impressum,kontakt,legal,privacy,terms,ueber-uns,about,support,hilfe,datenschutz`
*   **`SCRAPER_CRITICAL_PRIORITY_KEYWORDS`**:
    *   Description: Keywords for top-priority pages (e.g., "Impressum") if found as a standalone segment in a URL path.
    *   Example: `SCRAPER_CRITICAL_PRIORITY_KEYWORDS=impressum,kontakt,contact,imprint`
*   **`SCRAPER_HIGH_PRIORITY_KEYWORDS`**:
    *   Description: Keywords for high-priority pages (e.g., "Legal") if found as a standalone segment.
    *   Example: `SCRAPER_HIGH_PRIORITY_KEYWORDS=legal,privacy,terms,datenschutz,ueber-uns,about,about-us`
*   **`SCRAPER_MAX_KEYWORD_PATH_SEGMENTS`**:
    *   Description: Max path segments for a priority keyword (critical/high) to retain its highest score tier. Longer paths get a slight score penalty.
    *   Default: `3`
*   **`SCRAPER_EXCLUDE_LINK_PATH_PATTERNS`**:
    *   Description: Comma-separated URL path patterns. Links containing these are hard-excluded.
    *   Example: `SCRAPER_EXCLUDE_LINK_PATH_PATTERNS=/media/,/blog/,/video/,/hilfe-video/`
*   **`SCRAPER_MAX_PAGES_PER_DOMAIN`**:
    *   Description: Max pages to scrape per domain. `0` for no limit.
    *   Default: `20`
*   **`SCRAPER_MIN_SCORE_TO_QUEUE`**:
    *   Description: Minimum score a link needs from `find_internal_links` to be added to the scrape queue.
    *   Default: `40`
*   **`SCRAPER_SCORE_THRESHOLD_FOR_LIMIT_BYPASS`**:
    *   Description: When `SCRAPER_MAX_PAGES_PER_DOMAIN` is hit, only links scoring at/above this threshold will be processed, up to `SCRAPER_MAX_HIGH_PRIORITY_PAGES_AFTER_LIMIT`.
    *   Default: `80`
*   **`SCRAPER_MAX_HIGH_PRIORITY_PAGES_AFTER_LIMIT`**:
    *   Description: After `SCRAPER_MAX_PAGES_PER_DOMAIN` is met, this is the maximum number of *additional* pages that can be scraped if they meet/exceed `SCRAPER_SCORE_THRESHOLD_FOR_LIMIT_BYPASS`. Helps to get a few very high-priority pages without scraping too many if a site is large.
    *   Default: `5`

#### LLM (Gemini) Settings
*   **`GEMINI_API_KEY`** (Required): Your Google Gemini API key.
*   **`LLM_MODEL_NAME`**: Specific Gemini model.
    *   Default: `gemini-1.5-pro-latest`
*   **`LLM_TEMPERATURE`**: Controls LLM output randomness (0.0-1.0).
    *   Default: `0.5`
*   **`LLM_MAX_TOKENS`**: Max tokens for LLM response.
    *   Default: `8192` (increased from older default)
*   **`LLM_PROMPT_TEMPLATE_PATH`**: Path to LLM prompt template file, relative to project root.
    *   Default: `prompts/gemini_phone_validation_v1.txt`

#### Phone Number Normalization
*   **`TARGET_COUNTRY_CODES`**: Comma-separated ISO country codes (e.g., DE, CH, AT) for parsing hints.
    *   Default: `DE,CH,AT`
*   **`DEFAULT_REGION_CODE`**: Default region if a number can't be parsed with specific context.
    *   Default: `DE`

#### Logging Settings
*   **`LOG_LEVEL`**: Log level for the main run log file (DEBUG, INFO, WARNING, ERROR).
    *   Default: `INFO`
*   **`CONSOLE_LOG_LEVEL`**: Log level for console output.
    *   Default: `WARNING` (to keep console less verbose)

## 6. Troubleshooting

*   **`GEMINI_API_KEY` errors**: Ensure key is correct in `.env`, file is loaded, and key is active with permissions.
*   **Playwright browser issues**: Run `playwright install` in your venv.
*   **`FileNotFoundError` for input**: Verify `INPUT_EXCEL_FILE_PATH` in `.env` is correct and relative to project root.
*   **Scraping issues (blocks, CAPTCHAs)**: Adjust timeouts. For persistent blocks, advanced techniques (not currently in scope) may be needed. Check `RESPECT_ROBOTS_TXT`.
*   **Incorrect phone parsing**: Check `TARGET_COUNTRY_CODES`, `DEFAULT_REGION_CODE`. Refine regex or LLM prompt if needed.
*   **`ModuleNotFoundError`**: Ensure venv is active and `pip install -r requirements.txt` was successful.
*   **Scraper not finding enough/too many pages**:
    *   Adjust `TARGET_LINK_KEYWORDS`: too broad might find too much, too narrow might miss pages.
    *   Tune `SCRAPER_CRITICAL_PRIORITY_KEYWORDS` and `SCRAPER_HIGH_PRIORITY_KEYWORDS` for pages you absolutely need.
    *   Modify `SCRAPER_MIN_SCORE_TO_QUEUE`: a higher value makes it more selective.
    *   Adjust `SCRAPER_MAX_PAGES_PER_DOMAIN` to control volume.
    *   Use `SCRAPER_EXCLUDE_LINK_PATH_PATTERNS` to explicitly ignore irrelevant sections.
    *   Check `MAX_DEPTH_INTERNAL_LINKS`.
*   **Path too long errors (Windows)**:
    *   Reduce `FILENAME_COMPANY_NAME_MAX_LEN` in `.env`.
    *   Ensure your project root path is not excessively long.

For other issues, consult the run log file in the `output_data/[RunID]/` directory.
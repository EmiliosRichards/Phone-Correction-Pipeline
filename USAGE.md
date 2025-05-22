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
      - [Developer Logging Guidelines](#developer-logging-guidelines)
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
    *   Determines the `GivenURL` and pre-processes it.
    *   Calls `scrape_website` to navigate the site. This function uses advanced link prioritization and scoring. It returns scraped page details, a scraper status, and the *pathful canonical entry URL* for the site (e.g., `http://www.example.com/en/contact/`).
    *   If this *pathful canonical entry URL* hasn't been processed yet in this run (checked against `globally_processed_urls` cache):
        *   Regex extraction is performed on scraped content.
        *   The `LLMExtractorComponent` (now with retry logic) sends candidate numbers and context to Google Gemini.
        *   Raw LLM outputs for this *pathful canonical entry URL* are cached in `canonical_site_raw_llm_outputs`.
    *   The *true base domain* (e.g., `http://example.com`) for the input row is determined and stored.
4.  **Global Data Consolidation**: After Pass 1, all raw LLM outputs (from `canonical_site_raw_llm_outputs`, keyed by pathful canonical URLs) are aggregated based on their *true base domain*. The `process_and_consolidate_contact_data` function is then called once per unique true base domain. This function de-duplicates phone numbers found across all pages of that true base domain, aggregates their source details (including original input company names and specific page URLs), determines the best classification, and sorts them.
5.  **Output Generation (Pass 2 - Report Building)**: Uses the globally consolidated data (keyed by true base domain):
    *   **Final Contacts Report** (`Final Contacts.xlsx`): Generates one consolidated row per unique true base domain. Features an aggregated company name (e.g., `[TrueBaseDomain] - OriginalCompA - OriginalCompB`), aggregated original `GivenURL`s, and a prioritized list of up to 3 *eligible* phone numbers (filtered by type and 'Non-Business' classification). Each phone number shows its aggregated types and a list of all original input companies that sourced that specific number for the true base domain. (Formerly "Top Contacts Report")
    *   **Final Processed Contacts Report** (`Final_Processed_Contacts.xlsx`): A cleaner, more concise version of the "Final Contacts Report". It is generated by reading "Final Contacts.xlsx" and includes specific columns: Company Name, URL, Number, Number Type, Number Found At.
    *   **Summary Report** (`phone_validation_output_{RunID}.xlsx`): Remains one row per original input entry. Populates top phone numbers and statuses by looking up the globally consolidated data for the input row's true base domain.
    *   **Detailed LLM Extractions Report** (`All_LLM_Extractions_Report_{RunID}.xlsx`): Lists all unique phone numbers found by the LLM for each true base domain, with aggregated types, best classification, and source URLs.
    *   All reports, along with rotating detailed logs and intermediate data dumps, are saved to a run-specific output directory.

### Outputs
The main pipeline generates several outputs, organized within a run-specific directory:

*   **Final Contacts Report**: An Excel file (e.g., `output_data/[RunID]/Final Contacts.xlsx`). Filename configured by `TERTIARY_REPORT_FILE_NAME_TEMPLATE`. This is the primary report for outreach.
*   **Final Processed Contacts Report**: An Excel file (e.g., `output_data/[RunID]/Final_Processed_Contacts.xlsx`). Filename configured by `PROCESSED_CONTACTS_REPORT_FILE_NAME_TEMPLATE`.
*   **Summary Report**: An Excel file (e.g., `output_data/[RunID]/Pipeline_Summary_Report_[RunID].xlsx`). Filename configured by `OUTPUT_EXCEL_FILE_NAME_TEMPLATE`.
*   **Detailed LLM Extractions Report**: An Excel file (e.g., `output_data/[RunID]/All_LLM_Extractions_Report_[RunID].xlsx`).
*   **Run Metrics Report** (`run_metrics.md`): A Markdown file providing a summary of the pipeline run. It includes:
    *   Overall processing statistics (e.g., total rows, rows processed, rows successfully completed).
    *   A "Global Pipeline Errors" section detailing any errors that affected the entire pipeline's execution.
    *   A "Summary of Row-Level Failures" section, hierarchically organized by `stage_of_failure`, showing counts of failures at each stage.
    *   *Note:* This report might not be generated if the pipeline encounters a critical failure very early during its initialization phase. In such cases, the main `.log` file and console output are the primary sources for diagnosing these initial failures.
*   **Failed Rows Report** (`failed_rows_{run_id}.csv`): A CSV file that lists each input row that failed during processing. Key columns include:
    *   `CompanyName`: The name of the company.
    *   `GivenURL`: The URL provided for the company.
    *   `stage_of_failure`: The specific pipeline stage where the error occurred (e.g., "Scraping", "LLM Extraction", "Data Consolidation").
    *   `error_details`: A JSON string containing detailed information about the error.
    *   `log_timestamp`: The timestamp of when the error was logged.
*   **Run Log File**: A comprehensive, rotating log of the pipeline's execution (e.g., `output_data/[RunID]/pipeline_run_[RunID].log`). This file contains detailed operational messages, warnings, and errors, including contextual identifiers like `InputRowID`, `CompanyName`, and `file_identifier_prefix` (e.g., `CANONICAL_...` for LLM logs) to aid in debugging and tracing data flow.
*   **Scraped Content Files**: Cleaned text content from each successfully scraped webpage, stored in `output_data/[RunID]/scraped_content/cleaned_pages_text/`.
*   **LLM Prompt Input File**: The full prompt sent to the LLM for each company, in `output_data/[RunID]/llm_context/`.
*   **LLM Raw Output File**: The raw response received from the LLM, in `output_data/[RunID]/llm_context/`.

### Output Directory Structure
The default output directory structure looks like this:
```
output_data/
└── [RunID]/  (e.g., 20240520_113000)
    ├── pipeline_run_20240520_113000.log                 # Main run log file (rotating)
    ├── run_metrics.md                                   # Run metrics and failure summary
    ├── failed_rows_20240520_113000.csv                  # Report of failed rows
    ├── scraped_content/
    │   └── cleaned_pages_text/
    │       └── CompanyName__domain_hash_cleaned.txt
    │       └── ... (other cleaned text files)
    ├── llm_context/
    │   ├── CANONICAL_example_com_llm_full_prompt.txt
    │   ├── CANONICAL_example_com_llm_input_data.json
    │   ├── CANONICAL_example_com_llm_raw_output.json
    │   └── ...
    ├── Pipeline_Summary_Report_20240520_113000.xlsx       # Summary Report
    ├── All_LLM_Extractions_Report_20240520_113000.xlsx    # Detailed Report
    ├── Final Contacts.xlsx                                # Final Contacts Report
    └── Final_Processed_Contacts.xlsx                      # Final Processed Contacts Report
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
    *   Default: `Pipeline_Summary_Report_{run_id}.xlsx`
*   **`TERTIARY_REPORT_FILE_NAME_TEMPLATE`**
    *   Description: Template for the "Final Contacts Report" Excel file (formerly "Top Contacts Report"). `{run_id}` is replaced if included, though the current default is static.
    *   Default: `Final Contacts.xlsx`
*   **`PROCESSED_CONTACTS_REPORT_FILE_NAME_TEMPLATE`**
    *   Description: Template for the "Final Processed Contacts Report" Excel file. `{run_id}` is replaced if included.
    *   Default: `Final_Processed_Contacts.xlsx`
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
    *   Description: After `SCRAPER_MAX_PAGES_PER_DOMAIN` is met, this is the maximum number of *additional* pages that can be scraped if their link score meets/exceeds `SCRAPER_SCORE_THRESHOLD_FOR_LIMIT_BYPASS`. This allows the scraper to fetch a few crucial pages (like 'contact' or 'impressum') even if the general page limit for the domain has been reached, ensuring key contact pages are not missed on large websites.
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
*   **`LOG_LEVEL`**: Log level for the main run log file (e.g., `pipeline_run_{RunID}.log`). Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
    *   Default: `INFO`
    *   The main log file uses rotation (10MB chunks, 5 backups) to manage size.
    *   Log messages in this file are enhanced with contextual identifiers:
        *   `InputRowID`: The index of the input row being processed.
        *   `CompanyName`: The name of the company associated with the log entry.
        *   `file_identifier_prefix`: A prefix (e.g., `CANONICAL_`, `REGEX_`) used in LLM-related log messages to distinguish their origin or context.
*   **`CONSOLE_LOG_LEVEL`**: Log level for console output. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
    *   Default: `WARNING` (to keep console less verbose during normal operation).
    *   This can be set via the `CONSOLE_LOG_LEVEL` environment variable in your `.env` file. For example, set to `DEBUG` for more detailed console output during development or troubleshooting.

#### Developer Logging Guidelines
When contributing to the pipeline, adhere to the following logging best practices:
*   **Use Standard Logging Levels**:
    *   `DEBUG`: Detailed information, typically of interest only when diagnosing problems.
    *   `INFO`: Confirmation that things are working as expected.
    *   `WARNING`: An indication that something unexpected happened, or indicative of some problem in the near future (e.g., ‘disk space low’). The software is still working as expected.
    *   `ERROR`: Due to a more serious problem, the software has not been able to perform some function.
    *   `CRITICAL`: A serious error, indicating that the program itself may be unable to continue running.
*   **Include Contextual Identifiers**: When logging messages related to specific data processing, especially within loops or component-specific logic, include relevant identifiers:
    *   For row-specific processing: `logger.info(f"Processing {company_name} (Row ID: {input_row_id}): Starting scrape.")`
    *   For LLM-related activities: `logger.debug(f"{file_identifier_prefix}LLM prompt generated for {company_name}.")`
    *   This helps in tracing the lifecycle of data through the pipeline and pinpointing issues related to specific inputs or components.
*   **Be Clear and Concise**: Log messages should be understandable and provide enough information to diagnose issues without being excessively verbose at standard levels (INFO, WARNING).
*   **Consult the Main Log**: The `pipeline_run_{RunID}.log` is the primary source for detailed debugging. The new contextual identifiers are crucial for filtering and understanding the flow of operations within this log.

## 6. Troubleshooting

*   **`GEMINI_API_KEY` errors**: Ensure key is correct in `.env`, file is loaded, and key is active with permissions.
*   **Playwright browser issues**: Run `playwright install` in your venv.
*   **`FileNotFoundError` for input**: Verify `INPUT_EXCEL_FILE_PATH` in `.env` is correct and relative to project root.
*   **Scraping issues (blocks, CAPTCHAs)**: Adjust timeouts. For persistent blocks, advanced techniques (not currently in scope) may be needed. Check `RESPECT_ROBOTS_TXT`.
*   **Incorrect phone parsing**: Check `TARGET_COUNTRY_CODES`, `DEFAULT_REGION_CODE`. Refine regex or LLM prompt if needed.
*   **`ModuleNotFoundError`**: Ensure venv is active and `pip install -r requirements.txt` was successful. If `tenacity` is missing, this is the cause.
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
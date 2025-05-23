# Phone Validation Pipeline

## Project Overview

The Phone Validation Pipeline is a Python-based application designed to automate the process of finding, validating, and enriching phone numbers for a given list of companies. It aims to improve the accuracy of contact information by intelligently navigating websites, extracting data using multiple methods, and processing information through a configurable workflow.

The pipeline reads company data from a spreadsheet, performs web scraping with advanced link prioritization, extracts potential phone numbers using regular expressions and a Large Language Model (LLM), and generates comprehensive reports.

For a detailed summary of recent enhancements and a deeper dive into specific features, please see the [Pipeline Enhancements Summary](./docs/pipeline_enhancements_summary_20250520_165353.md) document and the [Report Enhancements: Final Processed Contacts](./docs/report_enhancements_final_processed_contacts.md) document.

## High-Level Workflow

The pipeline follows these main stages:

1.  **Data Ingestion**: Reads company data (name, website URL, existing phone number) from an input Excel/CSV file.
2.  **Web Scraping**: Intelligently navigates company websites using an advanced link prioritization and scoring system to gather text content, focusing on pages most likely to contain contact information.
3.  **Regex Extraction**: Applies regular expressions to the scraped text to identify potential phone number patterns and their surrounding context.
4.  **LLM Extraction**: Utilizes a Large Language Model (Google Gemini) to analyze the scraped text and contextual snippets to extract, confirm, and classify phone numbers.
5.  **Data Consolidation & Verification**: Consolidates all extracted data globally by *true base domain* (e.g., `http://example.com`). This handles variations in input URLs and ensures each unique website is processed efficiently. Phone numbers are de-duplicated per true base domain, and their original sources (including input company names and specific page URLs) and types are aggregated.
6.  **Reporting**: Generates several key outputs for each run:
    *   **Four primary Excel reports**:
        *   **Final Contacts Report** (`Final Contacts.xlsx`): One consolidated entry per unique true base domain. Features aggregated company names, a filtered and prioritized list of up to 3 phone numbers (with their types and original sourcing company names), and source URLs. This is the primary report for outreach. (Formerly "Top Contacts Report")
        *   **Final Processed Contacts Report** (`Final_Processed_Contacts.xlsx`): A cleaner, more concise version of the "Final Contacts Report", with specific columns: Company Name, URL, Number, Number Type, Number Found At. It uses the "Final Contacts.xlsx" as its direct data source.
        *   **Summary Report** (`phone_validation_output_{RunID}.xlsx`): One row per original input entry, showing top numbers found for its corresponding true base domain and verification statuses.
        *   **Detailed LLM Extractions Report** (`All_LLM_Extractions_Report_{RunID}.xlsx`): Lists all unique phone numbers found by the LLM for each true base domain, with aggregated types and source URLs.
    *   **Run Metrics Report** (`run_metrics.md`): A Markdown file summarizing the overall health of the pipeline run, including processing statistics, global errors, and a hierarchical summary of row-level failures by stage.
    *   **Failed Rows Report** (`failed_rows_{run_id}.csv`): A CSV file detailing input rows that encountered critical processing errors that halted their progress, including company information, the stage of failure, and specific error messages.
    *   **Row Attrition Report** (`row_attrition_report_{run_id}.csv`): A new CSV file detailing all input rows that did *not* result in a final extracted contact, providing specific reasons for non-extraction (e.g., `LLM_Output_NumbersFound_NoneRelevant_AllAttempts`, `Scraping_AllAttemptsFailed_Network`) and a fault category (e.g., "Website Issue", "LLM Issue"). This report helps track why input rows might be "lost" during the pipeline.
    Additionally, detailed (and now rotating) logs are created for traceability and debugging.
## Key Features & Technologies

*   **Automated Phone Number Retrieval**: Scrapes websites and intelligently extracts phone numbers.
*   **Advanced Link Prioritization & Scoring**: Web scraper uses a multi-tier scoring system to focus on relevant pages.
*   **Multi-Modal Extraction**: Combines regex and LLM techniques for robust extraction.
*   **Flexible LLM Output Handling**: LLM returns text-based JSON, parsed and validated by the application.
*   **True Base Domain Consolidation**: All data is globally consolidated by the true base domain (e.g., `http://example.com`), ensuring efficient processing and unified reporting for each unique website, regardless of input URL variations.
*   **Refined Quadruple Excel Reporting**:
    *   `Final Contacts Report`: Optimized for outreach, one row per true base domain, with filtered, prioritized contacts and aggregated company/source details.
    *   `Final Processed Contacts Report`: A lean, clean version of the `Final Contacts Report` for quick review.
    *   `Summary Report`: Per-input-row overview.
    *   `Detailed_LLM_Extractions_Report`: Comprehensive log of all numbers found by LLM per true base domain.
*   **Robust LLM Interaction**: Includes retry mechanisms for API calls to Google Gemini.
*   **Enhanced Logging**: Features rotating log files, configurable log levels (for file and console via `CONSOLE_LOG_LEVEL` environment variable), and detailed contextual information in logs (e.g., `InputRowID`, `CompanyName`, `file_identifier_prefix`) to aid debugging.
*   **Granular Outcome Reasons**: The main output Excel file (e.g., `phone_validation_output_{RunID}.xlsx`) now includes a `Final_Row_Outcome_Reason` column, providing specific explanations for rows that did not yield a contact.
*   **Advanced Scraper Configuration**: Includes options like `SCRAPER_MAX_HIGH_PRIORITY_PAGES_AFTER_LIMIT` for fine-tuned scraping.
*   **Highly Configurable**: Behavior can be customized extensively via a `.env` file.
*   **Configurable Filename Lengths**: Prevents path length errors by allowing configuration of company name length in output filenames.

**Technologies Used:**

*   **Python 3.x**
*   **Pandas**: For data manipulation and Excel/CSV file handling.
*   **Playwright**: For robust web scraping, including dynamic content.
*   **Beautiful Soup (bs4)**: For HTML parsing.
*   **python-phonenumbers**: For parsing, formatting, and validating phone numbers.
*   **Google Gemini API**: For LLM-based extraction and reasoning.
*   **python-dotenv**: For managing environment variables.
*   **Pydantic**: For data validation and settings management.

## Directory Structure Overview

```
phone_validation_pipeline/
├── .env.example           # Example environment variable configuration
├── main_pipeline.py       # Main script to run the entire pipeline
├── README.md              # This file
├── requirements.txt       # Python package dependencies
├── USAGE.md               # Detailed usage and configuration guide
├── data/                  # Default directory for input data files
│   └── data_to_be_inputed.csv # Example input
├── docs/                  # Project documentation
│   ├── pipeline_enhancements_summary_20250520_165353.md # Detailed summary of recent features
│   ├── report_enhancements_final_processed_contacts.md # Documentation for the "Final Processed Contacts" report
│   └── archive/                 # Older planning and summary documents
│       └── ...
├── prompts/               # Directory for LLM prompt templates
│   └── gemini_phone_validation_v1.txt
├── src/                   # Source code
│   ├── core/              # Core components (config, schemas, logging)
│   │   ├── config.py
│   │   ├── logging_config.py
│   │   └── schemas.py
│   ├── data_handler.py    # Handles data input and output
│   ├── llm_extractor_component.py # LLM extraction logic
│   ├── regex_extractor_component.py # Regex extraction logic
│   └── scraper/           # Web scraping logic
│       ├── __init__.py
│       └── scraper_logic.py
└── output_data/           # Default directory for pipeline outputs (created on run)
    └── [RunID]/           # Outputs for a specific pipeline run (e.g., 20240520_110000)
        ├── pipeline_run_{RunID}.log # Main, rotating log file for the run
        ├── run_metrics.md           # Run metrics, failure summary, and input row attrition summary
        ├── failed_rows_{RunID}.csv  # Detailed report of rows that critically failed processing
        ├── row_attrition_report_{RunID}.csv # New: Report detailing why input rows didn't yield contacts
        ├── scraped_content/
        │   └── cleaned_pages_text/  # Cleaned text from scraped pages
        ├── llm_context/
        │   ├── ..._llm_prompt_input.txt # Full prompt sent to LLM
        │   └── ..._llm_raw_output.json  # Raw LLM response
        ├── phone_validation_output_{RunID}.xlsx       # Summary report (per input row)
        ├── All_LLM_Extractions_Report_{RunID}.xlsx    # Detailed flattened report
        ├── Final Contacts.xlsx                        # Consolidated top contacts report (per true base domain)
        └── Final_Processed_Contacts.xlsx              # Leaner, processed version of Final Contacts
```

## Setup Instructions

Follow these steps to set up and run the Phone Validation Pipeline:

1.  **Clone the Repository (Conceptual)**:
    If this project were hosted on a Git platform (like GitHub), you would clone it. For now, ensure you have all the project files in a local directory.

2.  **Set up a Python Virtual Environment**:
    It's highly recommended to use a virtual environment.
    ```bash
    python -m venv venv
    ```
    Activate it:
    *   Windows: `.\venv\Scripts\activate`
    *   macOS/Linux: `source venv/bin/activate`

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright Browsers**:
    ```bash
    playwright install
    ```

5.  **Set up the `.env` File**:
    *   Copy the example file:
        *   Windows: `copy .env.example .env`
        *   macOS/Linux: `cp .env.example .env`
    *   Open `.env` and fill in required values, especially:
        *   `GEMINI_API_KEY`
        *   `INPUT_EXCEL_FILE_PATH` (relative to the project root, e.g., `data/your_input_file.csv`)
    *   Review all other variables in [`.env.example`](./.env.example) and adjust them based on the new features and your needs (e.g., scraper keywords, page limits, logging levels).

## Basic Usage

### Running the Main Pipeline

To process your input file and generate the enriched data and reports:
```bash
python main_pipeline.py
```
This script will:
*   Read data from the `INPUT_EXCEL_FILE_PATH` specified in your `.env` file.
*   Perform scraping, extraction, and validation according to the configured settings.
*   Save output files to a run-specific subdirectory within `output_data/` (e.g., `output_data/YYYYMMDD_HHMMSS/`). This includes:
    *   The Final Contacts Report (`Final Contacts.xlsx`).
    *   The Final Processed Contacts Report (`Final_Processed_Contacts.xlsx`).
    *   The Summary Report (`phone_validation_output_{RunID}.xlsx`).
    *   The Detailed LLM Extractions Report (`All_LLM_Extractions_Report_{RunID}.xlsx`).
    *   The Run Metrics Report (`run_metrics.md`).
    *   The Failed Rows Report (`failed_rows_{RunID}.csv`).
    *   The Row Attrition Report (`row_attrition_report_{RunID}.csv`).
    *   A comprehensive, rotating run log (`pipeline_run_{RunID}.log`).
    *   Subdirectories for scraped content and LLM context (prompts, raw responses).

## Advanced Usage & Configuration

For more detailed information on:
*   All environment variables and their effects (including the new scraper and logging configurations).
*   Input data format specifications.
*   Detailed explanation of pipeline outputs and report structures.
*   Advanced configuration options and best practices.
*   Troubleshooting common issues.

Please refer to the [**USAGE.md**](./USAGE.md) file, the [**Pipeline Enhancements Summary**](./docs/pipeline_enhancements_summary_20250520_165353.md) document, and the [**Report Enhancements: Final Processed Contacts**](./docs/report_enhancements_final_processed_contacts.md) document.
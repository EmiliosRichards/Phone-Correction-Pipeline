# Phone Validation Pipeline

## Project Overview

The Phone Validation Pipeline is a Python-based application designed to validate and enrich phone numbers from a given spreadsheet. It automates the process of finding correct phone numbers for companies by performing a series of steps: data ingestion, web scraping, regex-based phone number extraction, LLM-based phone number extraction, final verification, and reporting.

The primary goal is to improve the accuracy of contact information, particularly for businesses where phone numbers might be missing, outdated, or incorrectly formatted in an initial dataset.

## High-Level Workflow

The pipeline follows these main stages:

1.  **Data Ingestion**: Reads company data (name, website URL, existing phone number) from an input Excel/CSV file.
2.  **Web Scraping**: Navigates to the provided company websites to gather text content, focusing on pages likely to contain contact information (e.g., "Contact Us", "About Us", "Impressum").
3.  **Regex Extraction**: Applies regular expressions to the scraped text to identify potential phone number patterns.
4.  **LLM Extraction**: Utilizes a Large Language Model (Google Gemini) to analyze the scraped text and extract or confirm phone numbers, especially in cases where regex might fail or context is needed.
5.  **Verification**: Cross-references and validates the findings from regex and LLM methods.
6.  **Reporting**: Generates a processed output file with enriched data and a separate report highlighting entries that may require manual review.

## Key Features & Technologies

*   **Automated Phone Number Retrieval**: Scrapes websites and intelligently extracts phone numbers.
*   **Multi-Modal Extraction**: Combines regex and LLM techniques for robust extraction.
*   **Configurable**: Behavior can be customized via a `.env` file.
*   **Reporting**: Provides clear outputs for validated data and items needing review.

**Technologies Used:**

*   **Python 3.x**
*   **Pandas**: For data manipulation and Excel/CSV file handling.
*   **Playwright**: For robust web scraping, including dynamic content.
*   **Beautiful Soup (bs4)**: For HTML parsing (used alongside Playwright).
*   **python-phonenumbers**: For parsing, formatting, and validating phone numbers.
*   **Google Gemini API**: For LLM-based extraction and reasoning.
*   **python-dotenv**: For managing environment variables.
*   **Pydantic**: For data validation and settings management.

## Directory Structure Overview

```
phone_validation_pipeline/
├── .env.example           # Example environment variable configuration
├── main_pipeline.py       # Main script to run the entire pipeline
├── generate_report.py     # Script to generate summary reports
├── README.md              # This file
├── requirements.txt       # Python package dependencies
├── USAGE.md               # Detailed usage and configuration guide
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
    └── [RunID]/           # Outputs for a specific pipeline run
        ├── scraped_content/ # Raw scraped HTML/text
        ├── llm_context/     # LLM prompts and raw responses
        └── processed_data_with_phones.xlsx # Main output file
```

## Setup Instructions

Follow these steps to set up and run the Phone Validation Pipeline:

1.  **Clone the Repository (Conceptual)**:
    If this project were hosted on a Git platform (like GitHub), you would clone it using:
    ```bash
    git clone <repository_url>
    cd phone_validation_pipeline
    ```
    For now, ensure you have all the project files in a local directory.

2.  **Set up a Python Virtual Environment**:
    It's highly recommended to use a virtual environment to manage dependencies.
    ```bash
    python -m venv venv
    ```
    Activate the virtual environment:
    *   On Windows:
        ```bash
        .\venv\Scripts\activate
        ```
    *   On macOS/Linux:
        ```bash
        source venv/bin/activate
        ```

3.  **Install Dependencies**:
    Install all required Python packages using the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright Browsers**:
    Playwright requires browser binaries to be installed. Run the following command:
    ```bash
    playwright install
    ```
    This will download the default set of browsers (Chromium, Firefox, WebKit).

5.  **Set up the `.env` File**:
    The application uses a `.env` file to manage sensitive information and configurations.
    *   Copy the example file:
        ```bash
        # On Windows
        copy .env.example .env

        # On macOS/Linux
        cp .env.example .env
        ```
    *   Open the newly created `.env` file in a text editor.
    *   Fill in the required values, especially:
        *   `GEMINI_API_KEY`: Your API key for Google Gemini.
        *   `INPUT_EXCEL_FILE_PATH`: Path to your input data file (e.g., `data_to_be_inputed.csv` or `data_to_be_inputed.xlsx`). This path is relative to the `phone_validation_pipeline` directory.
        *   Review other variables and adjust if necessary (see [`.env.example`](./.env.example) for all options).

## Basic Usage

### Running the Main Pipeline

To process your input file and generate the enriched data:
```bash
python main_pipeline.py
```
This script will:
*   Read data from the `INPUT_EXCEL_FILE_PATH` specified in your `.env` file.
*   Perform scraping, extraction, and validation.
*   Save output files (processed data, scraped content, LLM context) to a run-specific subdirectory within `output_data/` (e.g., `output_data/YYYYMMDD_HHMMSS/`).

### Running the Reporting Script

After the main pipeline has run, you can generate a summary report and a file for manual review:
```bash
python generate_report.py <path_to_processed_excel_file>
```
Replace `<path_to_processed_excel_file>` with the actual path to the `processed_data_with_phones.xlsx` (or similarly named) file generated by `main_pipeline.py`. For example:
```bash
python generate_report.py output_data/20240516_103000/processed_data_with_phones.xlsx
```
You can also specify an output directory and run ID for the report:
```bash
python generate_report.py output_data/20240516_103000/processed_data_with_phones.xlsx --output_dir reports/ --run_id 20240516_103000
```

## Advanced Usage & Configuration

For more detailed information on:
*   All environment variables and their effects.
*   Input data format specifications.
*   Detailed explanation of pipeline outputs.
*   Advanced configuration options.
*   Troubleshooting common issues.

Please refer to the [**USAGE.md**](./USAGE.md) file.